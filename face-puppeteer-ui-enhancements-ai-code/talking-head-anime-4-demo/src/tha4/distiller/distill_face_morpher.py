from pathlib import Path

from tha4.distiller.distill_logging import configure_distill_logging, log_distill_project_banner
from tha4.distiller.distiller_config import DistillerConfig
from tha4.shion.core.training.distrib.distributed_trainer import DistributedTrainer

if __name__ == "__main__":
    configure_distill_logging()

    parser = DistributedTrainer.get_default_arg_parser()
    parser.add_argument('--config_file', type=str)
    args = parser.parse_args()

    config_file_name = args.config_file
    config = DistillerConfig.load(config_file_name)

    log_distill_project_banner(
        Path(config.prefix).name,
        Path(config.character_image_file_name).name,
        config.prefix,
    )

    DistributedTrainer.run_with_args(config.get_face_morpher_trainer, args)
