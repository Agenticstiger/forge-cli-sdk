# fluid-provider-sdk

Zero-dependency SDK for building [FLUID](https://open-data-protocol.github.io/fluid/) data product providers.

## Why a separate package?

Third-party provider authors only need the `BaseProvider` ABC and a handful of
types. Installing the full `fluid-build` CLI (~40 dependencies) just to develop
a provider is overkill. This SDK package has **zero external dependencies**.

## Install

```bash
pip install fluid-provider-sdk
```

## Quick Start

```python
from fluid_provider_sdk import BaseProvider, ApplyResult, ProviderError

class MyCloudProvider(BaseProvider):
    name = "mycloud"

    def plan(self, contract):
        return [{"op": "create_table", "resource_id": "t1"}]

    def apply(self, actions):
        import time
        start = time.time()
        results = []
        for action in actions:
            results.append({"op": action["op"], "status": "ok"})
        return ApplyResult(
            provider=self.name,
            applied=len(results),
            failed=0,
            duration_sec=round(time.time() - start, 3),
            timestamp="",
            results=results,
        )
```

Register via entry point in your `pyproject.toml`:

```toml
[project.entry-points."fluid_build.providers"]
mycloud = "my_package.provider:MyCloudProvider"
```

## API Reference

See the [Custom Providers Guide](https://agenticstiger.github.io/forge_docs/providers/custom-providers.html)
for the full guide.
