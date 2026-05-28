from tha4.distiller.distiller_config import (
    DistillerConfig,
    BODY_MORPHER_TRAINING_TARGET,
    BODY_MORPHER_FINAL_CHECKPOINT_INDEX,
    BODY_MORPHER_CHECKPOINT_INDEX_450K,
)

cfg = DistillerConfig.load("E:/THA4_bundle/distill_outputs/bai/config.yaml")
trainer = cfg.get_body_morpher_trainer(1)
assert trainer.training_protocol.get_checkpoint_examples()[-1] == BODY_MORPHER_TRAINING_TARGET
assert BODY_MORPHER_FINAL_CHECKPOINT_INDEX == 80
assert BODY_MORPHER_CHECKPOINT_INDEX_450K == 45
print("ok")
