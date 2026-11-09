from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Form
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from .captcha import create_challenge, verify_captcha
from .db import Contact, ContactCreate, ContactRead, get_session, init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Sito BE - Contatti", lifespan=lifespan)

SessionDep = Annotated[Session, Depends(get_session)]

CONTACT_FORM_HTML = """<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Contattaci</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 520px; margin: 2rem auto; padding: 0 1rem; }
    label { display: block; margin-top: 1rem; font-weight: 600; }
    input, textarea { width: 100%; padding: .5rem; box-sizing: border-box; font: inherit; }
    textarea { min-height: 150px; }
    button { margin-top: 1.25rem; padding: .6rem 1.2rem; font: inherit; cursor: pointer; }
    button:disabled { cursor: progress; opacity: .6; }
    .hp { position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden; }
    #status { margin-top: 1rem; }
    #status.ok { color: #1a7f37; }
    #status.err { color: #cf222e; }
  </style>
</head>
<body>
  <h1>Contattaci</h1>
  <form id="contact-form" method="post" action="/contacts">
    <label for="nome">Nome</label>
    <input id="nome" name="nome" required maxlength="100">
    <label for="cognome">Cognome</label>
    <input id="cognome" name="cognome" required maxlength="100">
    <label for="email">Email di contatto</label>
    <input id="email" name="email" type="email" required maxlength="255">
    <label for="messaggio">Perché ci stai contattando?</label>
    <textarea id="messaggio" name="messaggio" required maxlength="5000"></textarea>
    <div class="hp" aria-hidden="true">
      <label for="website">Non compilare questo campo</label>
      <input id="website" name="website" tabindex="-1" autocomplete="off">
    </div>
    <input type="hidden" name="captcha">
    <button type="submit">Invia</button>
    <p id="status" role="status" aria-live="polite"></p>
  </form>
  <script>
    const form = document.getElementById("contact-form");
    const statusEl = document.getElementById("status");
    const button = form.querySelector("button");
    const enc = new TextEncoder();

    function setStatus(text, cls = "") { statusEl.textContent = text; statusEl.className = cls; }

    async function sha256hex(text) {
      const buf = await crypto.subtle.digest("SHA-256", enc.encode(text));
      return Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, "0")).join("");
    }

    async function solveCaptcha() {
      const res = await fetch("/captcha/challenge");
      if (!res.ok) throw new Error("Impossibile ottenere il captcha");
      const c = await res.json();
      for (let n = 0; n <= c.maxnumber; n++) {
        if (await sha256hex(c.salt + n) === c.challenge) {
          return btoa(JSON.stringify({ salt: c.salt, number: n, challenge: c.challenge, signature: c.signature }));
        }
      }
      throw new Error("Captcha non risolto");
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      button.disabled = true;
      try {
        setStatus("Verifica anti-spam in corso…");
        form.elements.captcha.value = await solveCaptcha();
        setStatus("Invio in corso…");
        const res = await fetch(form.action, { method: "POST", body: new FormData(form) });
        if (res.ok) {
          form.reset();
          setStatus("Grazie! Il tuo messaggio è stato inviato.", "ok");
        } else {
          const body = await res.json().catch(() => ({}));
          const detail = typeof body.detail === "string" ? body.detail : "Controlla i campi del modulo.";
          setStatus("Errore: " + detail, "err");
        }
      } catch (err) {
        setStatus("Errore: " + err.message, "err");
      } finally {
        button.disabled = false;
      }
    });
  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def contact_form() -> str:
    return CONTACT_FORM_HTML


@app.get("/captcha/challenge")
def captcha_challenge() -> dict:
    return create_challenge()


@app.post(
    "/contacts",
    response_model=ContactRead,
    status_code=201,
    dependencies=[Depends(verify_captcha)],
)
def create_contact(data: Annotated[ContactCreate, Form()], session: SessionDep) -> Contact:
    contact = Contact.model_validate(data)
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact
