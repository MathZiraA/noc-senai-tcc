import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

smtp_server = "smtp.gmail.com"
port = 587
sender_email = "matheus.ziravello@gmail.com"
password = "<REMOVIDA>"
receiver_email = "matheus.ziravello@gmail.com"

msg = MIMEMultipart()
msg['From'] = sender_email
msg['To'] = receiver_email
msg['Subject'] = "🚨 [NOC SENAI] Teste de Notificacao de Enlaces"

body = """
<h3>Validação do Servidor de E-mail - NOC SENAI</h3>
<p>Este e-mail confirma que o servidor Debian e as credenciais do Gmail estão 100% operacionais.</p>
<hr>
<p><b>Status Zabbix Server:</b> Ativo (v7.0.31)</p>
<p><b>Ação Configurada:</b> Notificação automática em caso de queda/restabelecimento dos enlaces Fibra e Rádio.</p>
"""
msg.attach(MIMEText(body, 'html'))

print("[+] Conectando ao servidor SMTP do Gmail (smtp.gmail.com:587)...")
try:
    server = smtplib.SMTP(smtp_server, port)
    server.starttls()
    print("[+] Autenticando com a conta de e-mail...")
    server.login(sender_email, password)
    print("[+] Enviando mensagem de teste...")
    server.sendmail(sender_email, receiver_email, msg.as_string())
    server.quit()
    print("\n========================================================")
    print(" [✔] E-MAIL ENVIADO COM SUCESSO PARA MATHEUS.ZIRAVELLO@GMAIL.COM!")
    print("========================================================")
except Exception as e:
    print(f"\n[-] Erro de autenticação/conexão SMTP: {e}")
