# Novaeon Sentinel 9B (formerly "Novaeon Kev 9B Crypto")

The model trained by this pipeline was renamed from **Novaeon Kev 9B Crypto** (`novaeon-kev-9b-crypto`) to
**Novaeon Sentinel 9B** ([`NovaeonStudio/novaeon-sentinel-9b`](https://huggingface.co/NovaeonStudio/novaeon-sentinel-9b)).
The old name was never published.

- Model card (the text uploaded to Hugging Face): [`sentinel/MODEL_CARD.md`](sentinel/MODEL_CARD.md)
- How it works, evaluation, parity of the Mac builds, how to reproduce: [`docs/SENTINEL.md`](../docs/SENTINEL.md)
- Labeling guide: [`LABELING.md`](LABELING.md)
- Metrics: [`results/`](results/) (`v3-*` = the published model, `parity-*` = the MLX builds,
  `baseline-kev-9b.json` = the untuned Kev-9B, `choice-v3.json` = threshold selection; `v1-*` and `v2-*` are earlier
  training runs, kept for comparison)

This directory keeps its old name so the file paths in the pipeline scripts stay stable.
