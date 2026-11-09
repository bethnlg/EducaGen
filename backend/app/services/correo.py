"""Envío de correos por SMTP con TLS (I-10)."""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from ..config import config

log = logging.getLogger("educagen.correo")


def _plantilla(titulo: str, cuerpo_html: str) -> str:
    return f"""
<div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; color: #0f172a;">
  <div style="background: #0369a1; color: #fff; padding: 20px 24px; border-radius: 12px 12px 0 0;">
    <strong style="font-size: 20px;">EducaGen</strong>
  </div>
  <div style="background: #f0f9ff; padding: 24px; border-radius: 0 0 12px 12px;">
    <h2 style="font-size: 18px; margin-top: 0;">{titulo}</h2>
    {cuerpo_html}
  </div>
</div>"""


def enviar(para: str, asunto: str, texto: str, html: str) -> bool:
    if not config.SMTP_USUARIO or not config.SMTP_CONTRASENA:
        log.warning("SMTP no configurado. Correo para %s no enviado. Contenido:\n%s", para, texto)
        return False
    msg = EmailMessage()
    msg["From"] = f"EducaGen <{config.SMTP_USUARIO}>"
    msg["To"] = para
    msg["Subject"] = asunto
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as servidor:
        servidor.starttls(context=ssl.create_default_context())
        servidor.login(config.SMTP_USUARIO, config.SMTP_CONTRASENA)
        servidor.send_message(msg)
    return True


def enviar_recuperacion(para: str, nombre: str, enlace: str) -> bool:
    texto = (
        f"Hola {nombre}:\n\nRecibimos una solicitud para restablecer tu contraseña de EducaGen.\n"
        f"Abre este enlace para crear una nueva (vence en 1 hora y solo puede usarse una vez):\n\n{enlace}\n\n"
        "Si no lo solicitaste, ignora este correo; tu contraseña no cambiará."
    )
    html = _plantilla("Restablece tu contraseña", f"""
    <p>Hola <strong>{nombre}</strong>:</p>
    <p>Recibimos una solicitud para restablecer tu contraseña. Pulsa el botón para crear una nueva:</p>
    <p style="text-align: center; margin: 28px 0;">
      <a href="{enlace}" style="background: #facc15; color: #0f172a; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold;">Restablecer contraseña</a>
    </p>
    <p style="font-size: 13px; color: #475569;">El enlace vence en 1 hora y solo puede usarse una vez. Si no lo solicitaste, ignora este correo.</p>""")
    return enviar(para, "Restablece tu contraseña de EducaGen", texto, html)


def enviar_bienvenida(para: str, nombre: str) -> bool:
    texto = f"Hola {nombre}:\n\nTu cuenta de EducaGen fue creada correctamente. Ya puedes generar sílabos, rúbricas, exámenes y casos de estudio.\n\n{config.APP_URL}/login"
    html = _plantilla("Tu cuenta está lista", f"""
    <p>Hola <strong>{nombre}</strong>:</p>
    <p>Tu cuenta de EducaGen fue creada correctamente. Ya puedes generar sílabos, rúbricas, exámenes y casos de estudio desde tu Dashboard.</p>
    <p style="text-align: center; margin: 28px 0;">
      <a href="{config.APP_URL}/login" style="background: #facc15; color: #0f172a; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold;">Ir a EducaGen</a>
    </p>""")
    return enviar(para, "Bienvenida a EducaGen", texto, html)


def enviar_verificacion(para: str, nombre: str, enlace: str) -> bool:
    texto = (
        f"Hola {nombre}:\n\nConfirma tu correo institucional para activar tu cuenta de EducaGen.\n"
        f"Abre este enlace (vence en 24 horas y solo puede usarse una vez):\n\n{enlace}\n"
    )
    html = _plantilla("Confirma tu correo institucional", f"""
    <p>Hola <strong>{nombre}</strong>:</p>
    <p>Confirma tu correo institucional para activar tu cuenta de EducaGen.</p>
    <p style="text-align: center; margin: 28px 0;">
      <a href="{enlace}" style="background: #facc15; color: #0f172a; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold;">Confirmar correo</a>
    </p>
    <p style="font-size: 13px; color: #475569;">El enlace vence en 24 horas y solo puede usarse una vez.</p>""")
    return enviar(para, "Confirma tu correo de EducaGen", texto, html)
