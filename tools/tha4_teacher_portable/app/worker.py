"""Run the original THA4 trainers with transactional pause/autosave snapshots."""
import argparse
import gc
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path
from portable import ROOT, PROJECT_ROOT, WORKSPACE_ROOT, atomic_json, environment

os.environ.update(environment())
sys.path.insert(0, str(ROOT / 'src'))


class TrainingPaused(Exception):
    pass


class Monitor:
    def __init__(self, trainer, job, phase, completed, totals, rank, local_rank, world):
        self.trainer, self.job, self.phase = trainer, job, phase
        self.completed, self.totals = completed, totals
        self.rank, self.local_rank, self.world = rank, local_rank, world
        self.state = None
        self.saved_at = time.monotonic()
        self.noted_at = 0.
        self.first_seen = None
        self.started = time.monotonic()
        self.sequence = int(time.time())
        self.resume = Path(trainer.prefix) / 'resume'

    def publish(self, state='running', error=None):
        if self.rank != 0:
            return
        seen = self.state.examples_seen_so_far if self.state else 0
        if self.first_seen is None or self.first_seen == 0 < seen:
            self.first_seen = seen
            self.started = time.monotonic()
        elapsed = time.monotonic() - self.started
        rate = (seen - self.first_seen) / elapsed if elapsed > 0 else 0
        remaining = max(0, self.totals[self.phase] - seen)
        atomic_json(self.job / 'progress.json', dict(
            state=state, phase=self.phase, examples=seen, target=self.totals[self.phase],
            overall=(self.completed + seen) / sum(self.totals.values()),
            phase_eta_seconds=remaining / rate if rate > 0 and seen-self.first_seen >= 3 else None,
            examples_per_second=rate, updated=time.time(), error=error))

    def save(self):
        import torch.distributed as dist
        if self.state is None:
            return
        self.sequence += 1
        target = self.resume / ('slot-' + str(self.sequence % 2))
        if self.rank == 0:
            if target.resolve().parent != self.resume.resolve():
                raise RuntimeError('Snapshot path escapes its task')
            if target.exists():
                shutil.rmtree(target)
        dist.barrier()
        self.state.save(str(target), self.rank, lambda: self.trainer.barrier(self.local_rank))
        if self.rank == 0:
            atomic_json(self.resume / 'latest.json', dict(slot=target.name, examples=self.state.examples_seen_so_far))
        dist.barrier()
        self.saved_at = time.monotonic()

    def install(self):
        trainer = self.trainer
        original_load, original_batch = trainer.load_previous_training_state, trainer.get_next_training_batch
        def load(target, world, rank, local_rank, device):
            candidates = []
            marker = self.resume / 'latest.json'
            if marker.exists():
                value = json.loads(marker.read_text('utf-8'))
                if value.get('slot') in ('slot-0', 'slot-1'):
                    candidates.append(self.resume / value['slot'])
            candidates.extend(p for p in (self.resume / 'slot-0', self.resume / 'slot-1') if p not in candidates)
            for path in candidates:
                if trainer.can_load_training_state(str(path), world):
                    try:
                        self.state = trainer.load_training_state(str(path), rank, local_rank, device)
                        logging.info('Restored full THA4 state at %d examples from %s', self.state.examples_seen_so_far, path)
                        self.sequence = int(path.name[-1])  # next save must preserve this valid slot
                        self.publish()
                        return self.state
                    except (OSError, RuntimeError, EOFError) as exc:
                        logging.exception('Resume snapshot failed; trying previous complete save: %s', exc)
            self.state = original_load(target, world, rank, local_rank, device)
            self.publish()
            return self.state
        def batch(examples, world, device):
            import torch
            import torch.distributed as dist
            # Called at a completed-iteration boundary: count, weights, optimizer
            # and RNG all describe the same state. Every rank joins the save.
            flags = torch.tensor([int((self.job / 'stop.request').exists()),
                                  int(time.monotonic() - self.saved_at >= 30.)], dtype=torch.int64)
            if self.world > 1:
                dist.broadcast(flags, src=0)
            if flags[0].item() or flags[1].item():
                self.publish('saving')
                self.save()
            if flags[0].item():
                self.publish('paused')
                raise TrainingPaused()
            if time.monotonic() - self.noted_at >= .5:
                self.publish()
                self.noted_at = time.monotonic()
            return original_batch(examples, world, device)
        trainer.load_previous_training_state = load
        trainer.get_next_training_batch = batch


def prepare_config(job):
    """Resolve inputs outside COMPONENT_ROOT without starting distributed training."""
    from tha4.distiller.distiller_config import DistillerConfig
    os.chdir(ROOT)
    job = job.resolve()
    if not job.is_relative_to(WORKSPACE_ROOT.resolve()):
        raise ValueError('Training task must be inside the teacher workspace')
    settings = json.loads((job / 'settings.json').read_text('utf-8'))
    prefix = job / 'output'
    prefix.mkdir(exist_ok=True)
    config = DistillerConfig(prefix=prefix.as_posix(),
                             character_image_file_name=(job / 'inputs/character.png').as_posix(),
                             face_mask_image_file_name=(job / 'inputs/face_mask.png').as_posix(), **settings)
    config.check()
    config.save(str(job / 'config.yaml'))
    return config


def run(job, smoke_examples=0):
    import torch
    import torch.distributed as dist
    from tha4.charmodel.character_model import CharacterModel
    if not torch.cuda.is_available():
        raise RuntimeError('上游 THA4 教师训练需要可用的 NVIDIA CUDA GPU。')
    job = job.resolve()
    config = prepare_config(job)
    if config.num_gpus > torch.cuda.device_count():
        raise RuntimeError('所选 GPU 数量超过当前可用 CUDA 设备数量。')
    rank, local_rank, world = (int(os.environ.get(key, default)) for key, default in
                               [('RANK', '0'), ('LOCAL_RANK', '0'), ('WORLD_SIZE', '1')])
    dist.init_process_group('gloo')
    completed = 0
    totals = {'face': 1_000_000, 'body': 1_500_000}
    try:
        for phase, factory in [('face', config.get_face_morpher_trainer), ('body', config.get_body_morpher_trainer)]:
            trainer = factory(world, 'gloo')
            totals[phase] = trainer.checkpoint_examples[-1]
            monitor = Monitor(trainer, job, phase, completed, totals, rank, local_rank, world)
            monitor.install()
            try:
                target = smoke_examples or None
                trainer.train(world, rank, local_rank, target)
                monitor.save()
                monitor.publish('paused' if smoke_examples else 'running')
                if smoke_examples:
                    return
                if rank == 0:
                    destination = Path(config.character_model_prefix())
                    destination.mkdir(exist_ok=True)
                    shutil.copyfile(trainer.get_checkpoint_prefix(len(trainer.checkpoint_examples) - 1) + '/module_module.pt',
                                    destination / (phase + '_morpher.pt'))
                completed += totals[phase]
            except TrainingPaused:
                return
            finally:
                if trainer.summary_writer is not None:
                    trainer.summary_writer.close()
                for loader in (trainer.training_data_loader, trainer.validation_data_loader):
                    iterator = getattr(loader, '_iterator', None)
                    if iterator is not None:
                        iterator._shutdown_workers()
                for iterator in (trainer.training_data_loader_iter, trainer.validation_data_loader_iter):
                    shutdown = getattr(iterator, '_shutdown_workers', None)
                    if callable(shutdown):
                        shutdown()
                del monitor, trainer
                gc.collect()
                torch.cuda.empty_cache()
        if rank == 0:
            shutil.copyfile(config.character_image_file_name, config.character_model_character_png_file_name())
            CharacterModel(config.character_model_character_png_file_name(), config.character_model_face_morpher_file_name(),
                           config.character_model_body_morpher_file_name()).save(config.character_model_yaml_file_name())
            atomic_json(job / 'progress.json', dict(state='completed', phase='done', overall=1., updated=time.time()))
    finally:
        dist.destroy_process_group()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--smoke-examples', type=int, default=0)
    parser.add_argument('--check-config', action='store_true', help='Validate only; never starts training')
    args = parser.parse_args()
    if args.check_config:
        config = prepare_config(args.job)
        print(json.dumps(dict(ok=True, training_started=False, prefix=config.prefix,
                              component=str(ROOT), project=str(PROJECT_ROOT)), ensure_ascii=False))
        raise SystemExit(0)
    import signal
    def request_stop(signum, frame):
        (args.job / 'stop.request').touch(exist_ok=True)
    for name in ('SIGINT', 'SIGTERM', 'SIGBREAK'):
        value = getattr(signal, name, None)
        if value is not None:
            signal.signal(value, request_stop)
    logging.basicConfig(level=logging.INFO)
    try:
        run(args.job, args.smoke_examples)
    except Exception as exc:
        logging.exception('THA4 training failed')
        path = args.job / 'progress.json'
        previous = json.loads(path.read_text('utf-8')) if path.exists() else {}
        previous.update(state='failed', error=str(exc), updated=time.time())
        atomic_json(path, previous)
        raise
