# Adding a framework

1. Create `src/agentsdiagram/adapters/<framework>/` with:
   - `symbols.py`: tables of `root.LastName` symbols, with the library version you verified
     against, and `all_symbols()`.
   - `extract.py`: a class with `framework`, `markers` (bytes for the prefilter),
     `run_methods`, `extract(module, facts)` and `check(project)`.
2. In `extract`, iterate `module.calls` (source order; reverse it for post-order) and
   `module.bindings`. Register nodes with `facts.add(Def(...), call)` and relations with
   `facts.edge(source_key, kind, module, target_expression)`. Let the linker resolve the
   targets; do not resolve names yourself. Use `adapters/base.py` helpers (`arg`,
   `string_value`, `describe_model`, `elements`, `value_of`…).
3. Add the framework to `Framework` in `ir.py`, run `pnpm schema`, and register the adapter in
   `adapters/__init__.py`.
4. Add fixtures under `tests/fixtures/<short>/`, unit tests, oracle tests (import the fixtures
   with the real library) and the symbol drift test, and add the library to the `oracle`
   dependency group and to `.github/workflows/drift.yml`.
5. Optional, for plan and edit: `adapters/<framework>/edit.py` with a class implementing
   `FrameworkEditor` (`edit/engine.py`): `add_agent`, `add_tool`, `add_mcp`, `connect`,
   `set_model`, `export_spec` (raise `EditError` for what the framework does not have), using the
   `Doc` primitives in `edit/doc.py` and the helpers in `edit/codegen.py`. Register it in
   `EDITORS`. Disconnect, remove and instructions are generic. Add oracle tests that import the
   edited code with the real library (`tests/test_edit.py`).
6. Document coverage in `docs/adapters/<framework>.md` and the README table.
