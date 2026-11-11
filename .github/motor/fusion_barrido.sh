#!/usr/bin/env bash
# Barrido de la fusión automática: evalúa los PR claude/* abiertos (o solo SOLO_PR) y fusiona los que pasan.
# Lo llama .github/workflows/fusion.yml desde el directorio de trabajo, con el clon de main en ./main.
# Un PR que no pasa deja un aviso y no pone el flujo en rojo; solo un fallo de la API al fusionar lo pone en rojo.
# Variables: GH_TOKEN, ACTIVA («si» para fusionar), SOLO_PR (opcional), REPO.
# Cambios del motor (.github/motor/, 11/11/2026): además del sello, «Revisión del motor» tiene que haber salido bien
# sobre ese commit en GitHub, a la primera y sin fallos anteriores; se fusiona como mucho uno por vuelta y se deja
# un aviso para Jose en el PR.
set +e
set -u
export GIT_LFS_SKIP_SMUDGE=1
MAIN=${MAIN:-main}
# El barrido y sus programas se ejecutan desde una copia: fusionar un cambio del motor no puede cambiar lo que
# sigue ejecutando esta misma vuelta.
if [ -z "${FUSION_COPIA:-}" ]; then
  FUSION_COPIA=$(mktemp -d) || exit 1
  cp -R "$MAIN/.github/motor/." "$FUSION_COPIA/" || exit 1
  export FUSION_COPIA
  exec bash "$FUSION_COPIA/fusion_barrido.sh"
fi
FILTRO='select(.isDraft|not) | select(.isCrossRepository|not) | select(.headRefName|startswith("claude/")) | "\(.number) \(.headRefOid)"'
CAMPOS=number,headRefName,headRefOid,isDraft,isCrossRepository
if [ -n "${SOLO_PR:-}" ]; then
  prs=$(gh pr view "$SOLO_PR" -R "$REPO" --json "$CAMPOS" --jq "$FILTRO") || { echo "::warning::No se pudo leer el PR #$SOLO_PR."; exit 0; }
else
  prs=$(gh pr list -R "$REPO" --base main --state open --json "$CAMPOS" --jq ".[] | $FILTRO") || { echo "::warning::No se pudo listar los PR."; exit 0; }
fi
[ -z "$prs" ] && { echo "Ningún PR claude/* abierto."; exit 0; }

# Revisión del motor sobre un commit: sale bien solo si hay al menos una ejecución terminada con éxito y ninguna
# terminada de otra forma (salvo canceladas), todas a la primera (sin «volver a ejecutar» hasta que salga).
revision_motor() {
  local sha=$1 runs
  runs=$(gh api "repos/$REPO/actions/workflows/revision-motor.yml/runs?head_sha=$sha&per_page=50" \
    --jq '.workflow_runs[] | select(.head_sha == "'"$sha"'") | select(.event == "pull_request_target") | select(.path == ".github/workflows/revision-motor.yml") | "\(.status) \(.conclusion) \(.run_attempt) \(.html_url)"') \
    || { echo "no se pudo consultar la revisión del motor"; return 1; }
  local exito="" linea st co at url
  while read -r st co at url; do
    [ -z "$st" ] && continue
    [ "$st" != completed ] && { echo "la revisión del motor aún está en marcha"; return 1; }
    [ "$co" = cancelled ] && continue
    [ "$at" != 1 ] && { echo "la revisión del motor se volvió a ejecutar ($url)"; return 1; }
    [ "$co" != success ] && { echo "la revisión del motor puso reparos o falló ($url)"; return 1; }
    exito=$url
  done <<< "$runs"
  [ -z "$exito" ] && { echo "no hay revisión del motor terminada sobre este commit"; return 1; }
  echo "$exito"
}

fallos=0
while read -r pr sha; do
  [ -z "$pr" ] && continue
  echo "== PR #$pr ($sha)"
  git -C "$MAIN" fetch -q origin main || { echo "::warning::No se pudo traer main."; continue; }
  base=$(git -C "$MAIN" rev-parse origin/main)
  git -C "$MAIN" checkout -q "$base"
  git -C "$MAIN" worktree remove --force ../rama 2>/dev/null; rm -rf rama
  if ! git -C "$MAIN" fetch -q origin "pull/$pr/head" || ! git -C "$MAIN" -c filter.lfs.smudge= -c filter.lfs.process= -c filter.lfs.required=false worktree add -q --detach ../rama "$sha"; then
    echo "::warning::PR #$pr: no se pudo montar $sha (¿ha avanzado la rama?); queda para el siguiente barrido."; continue
  fi
  tok=$(openssl rand -hex 16)
  echo "::stop-commands::$tok"
  python3 "$FUSION_COPIA/fusion.py" --rama rama --base "$base" | tee puerta.txt; puerta=${PIPESTATUS[0]}
  motor=$(sed -n 's/^MOTOR: //p' puerta.txt | head -1)
  salud=9
  if [ $puerta -eq 0 ]; then python3 "$FUSION_COPIA/salud.py" --raiz rama; salud=$?; fi
  echo "::$tok::"
  git -C "$MAIN" worktree remove --force ../rama
  if [ $puerta -ne 0 ] || [ $salud -ne 0 ]; then
    echo "::warning::PR #$pr NO se fusiona (puerta=$puerta, salud=$salud)."; continue
  fi
  revision=""
  if [ -n "$motor" ]; then
    revision=$(revision_motor "$sha") || { echo "::warning::PR #$pr NO se fusiona: toca el motor y $revision."; continue; }
  fi
  if [ "${ACTIVA:-}" != "si" ]; then
    echo "::notice::SIMULACIÓN: el PR #$pr se fusionaría (FUSION_AUTOMATICA no es «si»)."; continue
  fi
  ahora=$(gh api "repos/$REPO/git/ref/heads/main" --jq .object.sha)
  if [ "$ahora" != "$base" ]; then
    echo "::warning::main se ha movido durante la comprobación; el PR #$pr queda para el siguiente barrido."; continue
  fi
  mensaje=$(git -C "$MAIN" log -1 --format=%B "$sha")
  titulo=$(git -C "$MAIN" log -1 --format=%s "$sha^")
  jq -n --arg sha "$sha" --arg t "$titulo (#$pr)" --arg m "$mensaje" \
    '{sha:$sha, merge_method:"squash", commit_title:$t, commit_message:$m}' > cuerpo.json
  if gh api -X PUT "repos/$REPO/pulls/$pr/merge" --input cuerpo.json >/dev/null; then
    echo "::notice::PR #$pr fusionado en main."
    if [ -n "$motor" ]; then
      # Todo lo que viene de la rama va dentro de un bloque de código y sin acentos graves: ni menciones ni enlaces.
      { printf 'Aviso para Jose: este cambio toca el motor de la web (no las páginas). Se ha publicado solo porque lo revisó otro modelo desde GitHub y salió limpio.\n\n'
        printf 'Revisión: %s\n\n```\n' "$revision"
        printf 'Qué cambia: %s\nFicheros: %s\n' "$titulo" "$motor" | tr -d '`'
        printf '```\n'; } > aviso.txt
      gh pr comment "$pr" -R "$REPO" --body-file aviso.txt >/dev/null \
        || echo "::warning::PR #$pr fusionado, pero no se pudo dejar el aviso del motor."
    fi
    # Lo que empuja el GITHUB_TOKEN no lanza flujos; «Después de publicar» se lanza a mano con el main anterior.
    gh workflow run publicacion.yml -R "$REPO" --ref main -f antes="$base" \
      || echo "::warning::PR #$pr fusionado, pero no se pudo lanzar «Después de publicar»: lanzarlo a mano."
    if [ -n "$motor" ]; then
      echo "::notice::Se ha fusionado un cambio del motor: el resto de PR queda para el siguiente barrido, con el motor nuevo."
      break
    fi
  else
    echo "::warning::La API no fusionó el PR #$pr."; fallos=1
  fi
done <<< "$prs"
exit $fallos
