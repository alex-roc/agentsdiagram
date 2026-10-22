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
5. Document coverage in `docs/adapters/<framework>.md` and the README table.
