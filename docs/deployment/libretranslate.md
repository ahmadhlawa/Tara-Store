# One shared private LibreTranslate service

Prepared configuration only; nothing has been deployed or tested on your server.
Keep this service outside application releases, for example
`/srv/shared/libretranslate`. Tara and other projects share its HTTP API, not
an Argos installation or translation container per project.

## Manual server preparation

Confirm Linux Docker Engine/Compose support, a free loopback port 5000, CPU/RAM/
disk capacity, and outbound access for initial image/model downloads.
Copy `deployment/libretranslate/compose.yml` into the shared directory.
Select a reviewed versioned image and record its immutable digest; the config
requires `LIBRETRANSLATE_IMAGE` and has no `latest` default. Verify the selected
image contains the documented scripts and model paths.
Use an image without bundled all-language models; the strict package check
below catches unexpected packages before you start the shared service.

The current upstream release is [v1.9.6](https://github.com/LibreTranslate/LibreTranslate/releases/tag/v1.9.6).
Confirm its Docker tag/architecture exists on your server, then pin its digest.
Example server commands, **not executed by this implementation**:

```bash
cd /srv/shared/libretranslate
export LIBRETRANSLATE_IMAGE=libretranslate/libretranslate:v1.9.6
docker compose config
docker compose pull
docker image inspect "$LIBRETRANSLATE_IMAGE" --format '{{index .RepoDigests 0}}'
# Set LIBRETRANSLATE_IMAGE to the recorded repo@sha256:... before installation.
```

Store the pinned value in the shared directory's `.env` for subsequent Compose
commands. This is separate from Tara's backend environment.

## Install only AR/EN models once

Bootstrap using the same volume as the long-running service:

```bash
docker compose run --rm --no-deps --entrypoint ./venv/bin/python libretranslate \
  scripts/install_models.py --load_only_lang_codes ar,en
docker compose run --rm --no-deps --entrypoint ./venv/bin/python libretranslate \
  -c 'from argostranslate import package; pairs={(p.from_code,p.to_code) for p in package.get_installed_packages()}; print(pairs); assert pairs == {("ar","en"),("en","ar")}'
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:5000/languages
curl --fail -H 'Content-Type: application/json' http://127.0.0.1:5000/translate \
  -d '{"q":"مرحبا","source":"ar","target":"en","format":"text"}'
curl --fail -H 'Content-Type: application/json' http://127.0.0.1:5000/translate \
  -d '{"q":"Hello","source":"en","target":"ar","format":"text"}'
```

Install both directional packages. The installer also obtains required
sentence-boundary assets. Normal startup uses `LT_LOAD_ONLY=ar,en` and
`LT_UPDATE_MODELS=false`; it reuses installed models. Argos runs locally with
`ARGOS_MODEL_PROVIDER=OPENNMT`.

Volume `shared-libretranslate-models` mounts `/home/libretranslate/.local`;
packages live under `.local/share/argos-translate/packages`. `XDG_CACHE_HOME`
is inside this volume so cached/sentence assets persist too, following upstream
[Compose guidance](https://github.com/LibreTranslate/LibreTranslate/blob/main/docker-compose.yml)
and [Argos paths](https://github.com/argosopentech/argos-translate/blob/master/argostranslate/settings.py).
Check write ownership against the pinned image's service UID (current upstream
Dockerfile uses UID/GID 1032). Named volumes normally initialize ownership from
the image; avoid an unwritable root-owned host bind directory.

Restart and recreate the container with the same volume; verify both directions
with outbound downloads unavailable and confirm no model re-download in logs.
Do not run `down -v`, prune/delete the volume, or rerun the forced installer on
ordinary deployments. Back up the volume and record package versions/checksums
before deliberate updates. Missing packages can trigger startup installation
attempts; both-direction checks and volume preservation enable offline restarts.

## Tara and other applications

For Tara running under systemd on this host:

```dotenv
LIBRETRANSLATE_URL=http://127.0.0.1:5000
LIBRETRANSLATE_API_KEY="" # Leave empty unless the service requires authentication.
TRANSLATION_ENABLED=true
TRANSLATION_TIMEOUT_SECONDS=15
```

Set these in Tara's backend environment and restart its backend after releasing
the code. Remove the obsolete Google key. No frontend env variable, public
Nginx translation route, new migration or backfill is needed. Existing migration
`0025_translations` must already be applied.

Containerized callers cannot use their own localhost. Attach this **same**
service and application containers to a dedicated private Docker network and
use `http://libretranslate:5000`; do not create another translation service.
Keep optional host publication on `127.0.0.1`. Remote hosts require a private
interface/VPN and firewall restrictions, not a public proxy.

Loopback trusts local processes. For project-specific API keys, enable service
key enforcement, persist its key database separately, and set each backend's
optional `LIBRETRANSLATE_API_KEY`. No browser access/CORS is needed.
Benchmark simultaneous projects and set host-appropriate CPU/memory limits;
one inference worker is configured initially. Outages delay English translation only; Arabic saves continue.
Self-hosting has no paid API charge but uses server resources. Review service/
model licenses when distributing modifications. Setup, real-model quality
checks, volume backups, network checks and server restarts remain manual work.
