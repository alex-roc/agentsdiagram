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
| VS Code Marketplace | publisher `alex-roc`; CI publishes with Microsoft Entra ID (no PAT) since 0.1.1 |
| Open VSX | namespace `alex-roc` verified (claim [EclipseFdn/open-vsx.org#14573](https://github.com/EclipseFdn/open-vsx.org/issues/14573) granted); published with `OVSX_PAT`. 0.1.0 and 0.1.1 stayed inactive (published before the claim) |

After the claim is approved: register a Trusted Publisher in Open VSX (Settings → Trusted
Publishers, namespace `alex-roc`, repo `alex-roc/agentsdiagram`, workflow `release.yml`,
environment `release`), switch the step to `npx ovsx publish --trusted-publishing` and delete
the `OVSX_PAT` secret. Trusted publishing needs an owned namespace and an existing extension.

## Marketplace via Entra ID (how it is wired)

- Tenant: personal *Default Directory* `complexooutlook.onmicrosoft.com`
  (`7c4a3e39-f90e-429b-abef-760378f49bf0`), created by an Azure free account. A personal
  Microsoft account alone has no tenant.
- App registration **`github-extension-publisher`** (client id
  `dbcdd7d2-ab8a-49fd-b1cb-f962a05fbc3b`), reusable for every extension: add one federated
  credential per repo (scenario *GitHub Actions*, entity *Environment* `release`). GitHub now
  issues immutable subjects, e.g. `repo:alex-roc@10243925/agentsdiagram@1429589378:environment:release`
  (check with `gh api repos/OWNER/REPO/actions/oidc/customization/sub`).
- Azure DevOps organization `alex-roc`, connected to that tenant; the service principal is a
  **Stakeholder** user there (free, does not use a Basic seat).
- Marketplace publisher member: the service principal's **global** identity id
  (`1a724d15-f7bf-4b2a-9177-69c23ac0de8f`, from `app.vssps.visualstudio.com/_apis/connectionData`),
  role Contributor. The organization-scoped id (`dev.azure.com/<org>/_apis/connectionData`) is
  rejected with TF14045, and `profiles/me` fails for service principals (VSS011031).
- `.github/workflows/marketplace-identity.yml` (manual) prints both ids and runs
  `vsce verify-pat` with the federated token: use it to set up or debug a new repo.
- Repository variables `AZURE_CLIENT_ID` / `AZURE_TENANT_ID`; `release.yml` runs `azure/login`
  and `vsce publish --azure-credential` in environment `release`.

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
