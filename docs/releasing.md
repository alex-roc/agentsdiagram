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

## Status (2026-10-22)

| Registry | State |
|---|---|
| PyPI | trusted publishing active (`release.yml`, environment `release`) |
| VS Code Marketplace | publisher `alex-roc`; v0.1.0 uploaded by hand from the GitHub release `.vsix`; CI publishing waits for Entra ID |
| Open VSX | namespace `alex-roc` created, ownership claim [EclipseFdn/open-vsx.org#14573](https://github.com/EclipseFdn/open-vsx.org/issues/14573); v0.1.0 published with `OVSX_PAT` but inactive until the claim is approved |

After the claim is approved: register a Trusted Publisher in Open VSX (Settings → Trusted
Publishers, namespace `alex-roc`, repo `alex-roc/agentsdiagram`, workflow `release.yml`,
environment `release`), switch the step to `npx ovsx publish --trusted-publishing` and delete
the `OVSX_PAT` secret. Trusted publishing needs an owned namespace and an existing extension.

## One-time setup

- **PyPI**: on pypi.org (account `alex-roc`), *Publishing → Add a pending publisher*:
  project `agentsdiagram`, owner `alex-roc`, repo `agentsdiagram`, workflow `release.yml`,
  environment `release`. Create the `release` environment in the GitHub repo.
- **Open VSX**: sign in at open-vsx.org with GitHub `alex-roc`, create an Eclipse account (with
  the GitHub username filled in) and sign the Publisher Agreement, create the namespace in
  Settings, then claim it ("Claim Ownership" opens an issue; option 1 needs the extension already
  on the Marketplace with this repo in `package.json`). The first version needs a token
  (`OVSX_PAT`); later versions can use trusted publishing.
- **Secrets**: set them in the GitHub web UI or from your own terminal. `gh secret set` inside a
  non-interactive shell stores an **empty** value.
- **VS Code Marketplace**: create publisher `alex-roc` at marketplace.visualstudio.com/manage
  (a `.vsix` can always be uploaded by hand there: New extension → Visual Studio Code).
  Global Azure DevOps PATs are retired on **2026-12-01**, so use Microsoft Entra ID: an app
  registration with a federated credential for `repo:alex-roc/agentsdiagram:environment:release`,
  added as a member of the publisher; set repository variables `AZURE_CLIENT_ID` and
  `AZURE_TENANT_ID`. (Until then a `VSCE_PAT` secret also works.) This needs your own Entra
  tenant (an Azure account; a personal Microsoft account alone has none) and an Azure DevOps
  organization connected to it, with the service principal added under Organization settings →
  Users (use the Object ID from *Enterprise applications*).

## Manual publish (fallback)

```bash
pnpm build && uv build && uv publish            # PyPI
pnpm --filter agentsdiagram run package         # packages/vscode/agentsdiagram-X.Y.Z.vsix
npx ovsx publish packages/vscode/*.vsix -p $OVSX_PAT
npx @vscode/vsce publish --packagePath packages/vscode/*.vsix --azure-credential
```
