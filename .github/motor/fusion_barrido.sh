#!/usr/bin/env bash
# Barrido de la fusión automática: evalúa los PR claude/* abiertos (o solo SOLO_PR) y fusiona los que pasan.
# Lo llama .github/workflows/fusion.yml desde el directorio de trabajo, con el clon de main en ./main.
# Un PR que no pasa deja un aviso y no pone el flujo en rojo; solo un fallo de la API al fusionar lo pone en rojo.
# Variables: GH_TOKEN, ACTIVA («si» para fusionar), SOLO_PR (opcional), REPO.
set +e
set -u
export GIT_LFS_SKIP_SMUDGE=1
MAIN=${MAIN:-main}
FILTRO='select(.isDraft|not) | select(.isCrossRepository|not) | select(.headRefName|startswith("claude/")) | "\(.number) \(.headRefOid)"'
CAMPOS=number,headRefName,headRefOid,isDraft,isCrossRepository
if [ -n "${SOLO_PR:-}" ]; then
  prs=$(gh pr view "$SOLO_PR" -R "$REPO" --json "$CAMPOS" --jq "$FILTRO") || { echo "::warning::No se pudo leer el PR #$SOLO_PR."; exit 0; }
else
  prs=$(gh pr list -R "$REPO" --base main --state open --json "$CAMPOS" --jq ".[] | $FILTRO") || { echo "::warning::No se pudo listar los PR."; exit 0; }
fi
[ -z "$prs" ] && { echo "Ningún PR claude/* abierto."; exit 0; }
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
  python3 "$MAIN/.github/motor/fusion.py" --rama rama --base "$base" | tee puerta.txt; puerta=${PIPESTATUS[0]}
  motor=$(sed -n 's/^MOTOR: //p' puerta.txt)
  salud=9
  if [ $puerta -eq 0 ]; then python3 "$MAIN/.github/motor/salud.py" --raiz rama; salud=$?; fi
  echo "::$tok::"
  git -C "$MAIN" worktree remove --force ../rama
  if [ $puerta -ne 0 ] || [ $salud -ne 0 ]; then
    echo "::warning::PR #$pr NO se fusiona (puerta=$puerta, salud=$salud)."; continue
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
      repaso=$(printf '%s\n' "$mensaje" | grep -i 'repaso *:' | head -1)
      printf 'Aviso para Jose: este cambio toca el motor de la web, no las páginas, y se ha publicado solo porque lo revisó otro modelo.\n\nQué cambia: %s\n\n%s\n\nFicheros del motor: %s\n' \
        "$titulo" "$repaso" "$motor" > aviso.txt
      gh pr comment "$pr" -R "$REPO" --body-file aviso.txt >/dev/null \
        || echo "::warning::PR #$pr fusionado, pero no se pudo dejar el aviso del motor."
    fi
    # Lo que empuja el GITHUB_TOKEN no lanza flujos; «Después de publicar» se lanza a mano con el main anterior.
    gh workflow run publicacion.yml -R "$REPO" --ref main -f antes="$base" \
      || echo "::warning::PR #$pr fusionado, pero no se pudo lanzar «Después de publicar»: lanzarlo a mano."
  else
    echo "::warning::La API no fusionó el PR #$pr."; fallos=1
  fi
done <<< "$prs"
exit $fallos
