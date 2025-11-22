"""Verify Pipeline 2 integration."""
from utils.pipelines import initialize_pipelines
from utils.processing_pipeline import get_pipeline_registry

print("="*60)
print("PIPELINE 2 INTEGRATION VERIFICATION")
print("="*60)
print()

# Get registry
registry = get_pipeline_registry()

# List all pipelines
print("Available Pipelines:")
for pipeline_meta in registry.list_pipelines():
    if hasattr(pipeline_meta, 'name'):
        print(f"  - {pipeline_meta.name}")
    else:
        print(f"  - {pipeline_meta['name']}")

print()
print(f"Current Active: {registry.active_pipeline_id}")
print()

# Test Pipeline 2
print("Testing Pipeline 2:")
registry.set_active_pipeline('adaptive')
pipeline2 = registry.get_pipeline('adaptive')

print(f"  Class: {type(pipeline2).__name__}")
print(f"  Name: {pipeline2.name}")
print(f"  Description: {pipeline2.description}")
print()

# Test metadata
metadata = pipeline2.get_metadata()
print("Pipeline 2 Metadata:")
for key, value in metadata.items():
    print(f"  {key}: {value}")

print()
print("="*60)
print("[+] Pipeline 2 is ready for use!")
print("="*60)
