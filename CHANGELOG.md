# Changelog

## [0.1.0](https://github.com/rendobar/rendobar-python/compare/rendobar-v0.1.0...rendobar-v0.1.0) (2026-11-22)


### Features

* LangChain and CrewAI agent tools, jobs.schema() ([83f0b5e](https://github.com/rendobar/rendobar-python/commit/83f0b5e58a49ba965bc90433508a180560e668a1))
* own retries, one error hierarchy, UnknownJob on every job call ([872bb9d](https://github.com/rendobar/rendobar-python/commit/872bb9dc340dfc3d8aaf2018870cf7d1a87e93d8))
* Rendobar Python SDK ([fec0818](https://github.com/rendobar/rendobar-python/commit/fec0818d513cb91184c5eddbbb1575a8967a67d2))


### Bug Fixes

* a rate-limited submit hands the agent its idempotency key ([5564d8a](https://github.com/rendobar/rendobar-python/commit/5564d8a6e6196aed69620444dbad4dcba1e92735))
* agent run_job never invites a duplicate billed job ([ba89d1c](https://github.com/rendobar/rendobar-python/commit/ba89d1c95753c13d5d0d7d1bff31886bda294140))
* keep the UnknownJob fallback typed for pyright ([76f608c](https://github.com/rendobar/rendobar-python/commit/76f608c27adac3cd9bedd3ab41d9f790634159df))
* refuse a blank webhook secret and never raise on a non-hex signature ([579faba](https://github.com/rendobar/rendobar-python/commit/579fabafbef8ada5cab57bb4f29e2e6f50a9c286))
* typed results, README corrections and clearer errors ([#3](https://github.com/rendobar/rendobar-python/issues/3)) ([e70a1c3](https://github.com/rendobar/rendobar-python/commit/e70a1c36d0607a72571d1428976a182d2fb88ea0))


### Documentation

* README matches the retry policy, error hierarchy, lifecycle and UnknownJob ([35503e7](https://github.com/rendobar/rendobar-python/commit/35503e7170ae3d18eef678827dcd9d3e053c27e2))
* tested FastAPI and Django examples ([c7df263](https://github.com/rendobar/rendobar-python/commit/c7df263bed007371684efc1565ecdfde84eb1c94))
