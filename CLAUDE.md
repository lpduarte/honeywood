# The Honeywood File — guia do projeto

Emails de H. B. Creswell, **"The Honeywood File" (1929)**, carta a carta, no dia de
calendário em que ocorrem no livro. Mapeamento de datas: **ano do livro + 102** →
ano real (1924→2026, 1925→2027, 1926→2028; dia/mês preservados). Cada carta é "recebida"
como se acontecesse hoje, ao longo de ~3 anos. Projeto pessoal, não comercial.

**Estado: LIVE.** Primeiro envio 14 Jun 2026; último 14 Fev 2028. Livro inteiro já
limpo (375 registos). Arquivo público em https://lpduarte.github.io/honeywood/.

## Como trabalho aqui (regras)

Estas são específicas do projeto — somam-se ao `~/.claude/CLAUDE.md` global.

1. **Reprodução fiel do livro.** Não acrescentar artefactos que não estão no texto
   original (papéis inventados, marcadores, anotações). Os erros do próprio livro são
   reproduzidos *verbatim*, nunca "corrigidos". → memória `feedback-faithful-reproduction`.
2. **Eu trato de todo o git flow.** branch → commit → push → PR → `gh pr merge` para
   `main`. O utilizador nunca faz merge à mão. Mas nunca commito para `main` direto, e
   só avanço quando a mudança foi aprovada. → `feedback_git_flow_owner`.
3. **Auditar à vontade, modificar com relutância.** Ler é grátis; o risco está nas
   alterações. Não "melhorar" código sem sintoma — sobretudo o caminho de envio
   (`send.py`), que exige razão forte + teste. Separar "está partido" de "podia ser
   diferente"; agir só no primeiro. → `feedback-modifications-caution`.
4. **Privacidade dos subscritores.** Endereços NUNCA no repo (é público). Vivem só num
   gist privado; editar via `manage_recipients.py`, nunca no repo. Um email por
   destinatário (To = essa pessoa, token de unsubscribe individual). → `feedback-recipient-privacy`.

O utilizador valoriza design visual, tipografia e UX. Discutir o design antes de mudar
algo visual. Português nas respostas.

## Estrutura

```
data/
  letters.json      registos estruturados (id L{page}-{n}, seq, book_date, send_date, from/to, body, commentary…)
  cleaned.json      corpo+comentário polidos por carta — merge sobre letters.json em load_merged()
  sent_log.json     dias já enviados (idempotência); committed de volta pelo workflow
source/             pipeline (ver abaixo)
worker/             Cloudflare Worker: unsubscribe + cron (dispara o workflow)
site/               output gerado do arquivo (NÃO editar à mão; build_site.py reescreve)
assets/             PNGs do pattern/ring/etc. (gerados por gen_assets.py, committed)
reference/          (gitignored) ferramenta de revisão OCR↔EPUB + cache de scans → memória project-epub-crosscheck
.github/workflows/  honeywood.yml (send+deploy, 2 crons), site.yml (rebuild on push), test.yml
```

**`send_date` vs `book_date`:** normalmente `send_date = book_date + 102 anos`. **Exceção
intencional — enclosures:** uma carta encerrada noutra tem `enclosure: true` e o `send_date`
da carta de **cobertura** (para chegarem no mesmo email, na ordem do livro); o `book_date`
mantém-se a data real. Os renderizadores mostram "Enclosure · «data própria»". **Não "corrigir"
essa divergência** — é deliberada (ver commit "Deliver enclosures with their covering letter").

**Data-flow:** OCR (`source/ocr_text/`) → `extract.py`/`parse.py` → `letters.json` →
limpeza manual → `cleaned.json` → **`render_email.py`** (email) e **`build_site.py`**
(site) → `send.py` (Gmail SMTP).

**Ficheiros-chave em `source/`:**
- `build.py` — `load_merged()` (junta letters+cleaned) e `group_by_send_date()`. Importado por quase tudo.
- `render_email.py` — **renderizador de email autoritativo** (email-safe: estilos inline + table layout). `email_day(letters, unsub_url=...)`, `subject_line()`.
- `build_site.py` — gera `./site` (calendário + páginas de leitura). Só revela cartas com `send_date <= hoje`.
- `send.py` — envia o dia via Gmail SMTP. `--date`, `--catchup`, `--dry-run`, `--check`, `--force`.
- `money.py` — conversão £(1924-26)→€ hoje, partilhada por email e site ("In today's money").
- `metric.py` — conversão imperial→métrico (comprimento/peso/área), bloco **"In metric"** sob o do
  dinheiro, partilhado por email e site. Apanha abreviaturas, hifenizadas (`2-in.`) e por extenso
  (`Four feet nine`); áreas da disputa da janela vão a m². O texto das cartas fica **imperial intacto**
  (só o bloco converte). Salta notas que explicam o próprio sistema imperial (`_EXPLAINS_IMPERIAL`,
  ex. a nota da "área superficial" em L158-0 — convertê-la seria contrassenso).
- `recipients.py` / `manage_recipients.py` — lista de destinatários (gist privado) e CLI.
- `render.py` — renderizador de dia mais antigo, usado só pelo `__main__` de `build.py`; o email real vai por `render_email.py`.
- Pipeline/QA: `extract.py`, `parse.py`, `rekey.py`, `qa_*.py`, `show_batch.py`, `show_uncleaned.py`, `test_data.py` (guard em CI).

**Config:** `.env` na raiz (gitignored): `GMAIL_USER`, `GMAIL_APP_PASSWORD`,
`RECIPIENTS_GIST_ID`, `RECIPIENTS_GIST_TOKEN`. `send.py` lê-o via `load_env()`.

## Playbook local (preview & teste)

**Preview de email (oficial):**
```
python3 source/send.py --date 2026-08-01 --dry-run   # escreve /tmp/mail_2026-08-01.html (não envia, não toca no gist)
```
Nota: o argumento é a **send_date** (ano real), não a book_date. book_date 1924-08-01 → send_date 2026-08-01.

**Ver no browser:** o Playwright MCP **bloqueia `file://`** — servir por HTTP:
```
cd /tmp && python3 -m http.server 8731    # depois navegar para http://localhost:8731/mail_2026-08-01.html
```

**Preview de uma página do site para um dia FUTURO:** `build_site.py` só escreve dias
já revelados. Para pré-visualizar um dia futuro, importar as suas funções sem disparar
o build (executar o ficheiro até ao marcador `# ---------- write ----------`) e chamar
`card_html(rec)` + `page(CSS_READ, …)` para o registo desse dia. (Hack pontual; não há
comando próprio.)

**Enviar preview real só para mim** (sem tocar no `sent_log` nem na lista): replicar o
corpo de `_send_day` com `recipients=[('lpduarte@gmail.com','TESTSAMPLE')]`, ou um
script SMTP curto que renderize `email_day(...)` e envie só para esse endereço. Assunto
prefixado `[PREVIEW]`.

## Ops

`honeywood.yml` faz send → rebuild → deploy Pages num só run, em 2 crons diários
(11:00 e 17:00 UTC). O cron real é um **Cloudflare Cron Trigger** (`worker/wrangler.toml`)
que dispara `workflow_dispatch` (o `on: schedule` do GitHub foi retirado por ser
impontual). Gráfico de atraso do cron (operacional, não linkado) em `/status.html`.
→ memórias `project-ops-status-dashboard`, `project-send-partial-failure`.
