# Releasing

Versions are kept in lockstep: `src/agentsdiagram/__init__.py` and `packages/vscode/package.json`
must match the tag. The extension runs `uvx agentsdiagram[lsp]==<its version>`, so PyPI is
published first.

```bash
# bump both versions, update CHANGELOG.md, commit
git tag v0.1.0 && git push origin v0.1.0
```

`.github/workflows/release.yml` builds the viewer, the wheel/sdist (checking `_static/` is inside)
and the `.vsix`, then publishes PyPI → Open VSX + Marketplace → GitHub release.

## One-time setup

- **PyPI**: on pypi.org (account `alex-roc`), *Publishing → Add a pending publisher*:
  project `agentsdiagram`, owner `alex-roc`, repo `agentsdiagram`, workflow `release.yml`,
  environment `release`. Create the `release` environment in the GitHub repo.
- **Open VSX**: sign in at open-vsx.org with GitHub `alex-roc`, sign the Publisher Agreement,
  create a token, run `npx ovsx create-namespace alex-roc -p <token>`, then claim the namespace
  (issue in EclipseFdn/open-vsx.org, "Namespace access"). Store the token as secret `OVSX_PAT`.
- **VS Code Marketplace**: create publisher `alex-roc` at marketplace.visualstudio.com/manage.
  Global Azure DevOps PATs are retired on **2026-12-01**, so use Microsoft Entra ID: an app
  registration with a federated credential for `repo:alex-roc/agentsdiagram:environment:release`,
  added as a member of the publisher; set repository variables `AZURE_CLIENT_ID` and
  `AZURE_TENANT_ID`. (Until then a `VSCE_PAT` secret also works.)

## Manual publish (fallback)

```bash
pnpm build && uv build && uv publish            # PyPI
pnpm --filter agentsdiagram run package         # packages/vscode/agentsdiagram-X.Y.Z.vsix
npx ovsx publish packages/vscode/*.vsix -p $OVSX_PAT
npx @vscode/vsce publish --packagePath packages/vscode/*.vsix --azure-credential
```
