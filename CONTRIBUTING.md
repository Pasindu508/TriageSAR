# Contributing

Thank you for helping. A few rules keep the project honest.

## Ground rules

1. **No invented numbers.** Every value shown in the UI, the API or the docs must be computed from a real
   product, or be shown as "not computed". Synthetic data live only under `tests/` and `.cache/`, are
   labelled `TEST ONLY`, and are never registered in `data/fixtures/`.
2. **No overclaiming.** The output is an *inspection priority*, never a damage probability, an accuracy, or a
   statistical confidence. A test (`test_no_overclaiming_language_anywhere_in_results`) guards this.
3. **Thresholds live in `config/triagesar.toml`** with a written rationale. Do not tune them to make a demo
   look better.
4. **Corrections are never applied silently.** If you apply one, record the layer in the manifest and add a test.
5. Use British English in UI copy and documentation.

## Workflow

```bash
make setup        # Python 3.12 venv + npm ci
make lint typecheck test
make test-e2e     # Playwright, uses the TEST ONLY synthetic event
```

Add or update tests with every change to `science/`. Tests must not need the network; tests that do must be
marked `@pytest.mark.integration` and skip unless `TRIAGESAR_RUN_INTEGRATION=1`.

Contributions are accepted under the Apache-2.0 licence of the project.
