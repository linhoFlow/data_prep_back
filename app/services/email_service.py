import smtplib
import random
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

class EmailService:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.username = os.getenv("SMTP_USERNAME", "jadonplimesancho117@gmail.com")
        self.password = os.getenv("SMTP_PASSWORD", "vzvx tvxl jfei lued")
        self.sender_email = self.username

    def send_admin_new_manager_notification(self, admin_email, manager_name, manager_email):
        """
        Notifie l'admin qu'un nouveau gestionnaire s'est inscrit.
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = f"DataPrep Pro <{self.sender_email}>"
            msg['To'] = admin_email
            msg['Subject'] = "DataPrep Pro - Nouveau Gestionnaire à Approuver"

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    .container {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px; border-radius: 20px; border: 1px solid #e2e8f0; color: #0A2647; }}
                    .logo {{ font-size: 24px; font-weight: bold; color: #0A2647; text-align: center; margin-bottom: 30px; }}
                    .logo span {{ color: #0061FF; }}
                    .content {{ line-height: 1.6; }}
                    .info-box {{ background: #f8fafc; border-radius: 12px; padding: 20px; margin: 24px 0; border-left: 4px solid #0061FF; }}
                    .footer {{ margin-top: 40px; font-size: 13px; color: #94a3b8; text-align: center; padding-top: 20px; border-top: 1px solid #f1f5f9; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="logo">Data<span>Prep</span> Pro</div>
                    <div class="content">
                        <h2>Nouveau Gestionnaire</h2>
                        <p>Un nouvel utilisateur s'est inscrit en tant que <strong>gestionnaire</strong> et attend votre approbation pour accéder au portail.</p>
                        <div class="info-box">
                            <strong>Nom :</strong> {manager_name}<br>
                            <strong>Email :</strong> {manager_email}
                        </div>
                        <p>Connectez-vous à l'espace administrateur pour activer ce compte.</p>
                    </div>
                    <div class="footer">Équipe DataPrep Pro &bull; Sécurité & Administration</div>
                </div>
            </body>
            </html>
            """
            msg.attach(MIMEText(html_body, 'html'))
            self._send(admin_email, msg)
            return True, None
        except Exception as e:
            return False, str(e)

    def send_manager_status_update(self, target_email, is_active):
        """
        Notifie le gestionnaire que son statut a changé.
        """
        status_text = "activé" if is_active else "désactivé"
        color = "#10b981" if is_active else "#ef4444"
        try:
            msg = MIMEMultipart()
            msg['From'] = f"DataPrep Pro <{self.sender_email}>"
            msg['To'] = target_email
            msg['Subject'] = f"DataPrep Pro - Compte {status_text.capitalize()}"

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    .container {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px; border-radius: 20px; border: 1px solid #e2e8f0; color: #0A2647; }}
                    .logo {{ font-size: 24px; font-weight: bold; color: #0A2647; text-align: center; margin-bottom: 30px; }}
                    .logo span {{ color: #0061FF; }}
                    .status-badge {{ display: inline-block; padding: 8px 16px; border-radius: 20px; background: {color}15; color: {color}; font-weight: bold; margin: 20px 0; }}
                    .footer {{ margin-top: 40px; font-size: 13px; color: #94a3b8; text-align: center; padding-top: 20px; border-top: 1px solid #f1f5f9; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="logo">Data<span>Prep</span> Pro</div>
                    <div class="content" style="text-align: center;">
                        <h2>Mise à jour de votre compte</h2>
                        <p>L'administrateur a mis à jour votre statut de gestionnaire :</p>
                        <div class="status-badge">Compte {status_text}</div>
                        <p>{"Vous pouvez désormais vous connecter à votre espace." if is_active else "Votre accès a été suspendu par l'administrateur."}</p>
                    </div>
                    <div class="footer">Équipe DataPrep Pro &bull; Gestion des Accès</div>
                </div>
            </body>
            </html>
            """
            msg.attach(MIMEText(html_body, 'html'))
            self._send(target_email, msg)
            return True, None
        except Exception as e:
            return False, str(e)

    def send_manager_deletion_notification(self, target_email):
        """
        Notifie le gestionnaire que son compte a été supprimé.
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = f"DataPrep Pro <{self.sender_email}>"
            msg['To'] = target_email
            msg['Subject'] = "DataPrep Pro - Suppression de votre compte"

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    .container {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px; border-radius: 20px; border: 1px solid #e2e8f0; color: #0A2647; }}
                    .logo {{ font-size: 24px; font-weight: bold; color: #0A2647; text-align: center; margin-bottom: 30px; }}
                    .logo span {{ color: #0061FF; }}
                    .footer {{ margin-top: 40px; font-size: 13px; color: #94a3b8; text-align: center; padding-top: 20px; border-top: 1px solid #f1f5f9; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="logo">Data<span>Prep</span> Pro</div>
                    <div class="content">
                        <h2>Compte Supprimé</h2>
                        <p>Nous vous informons que votre compte de gestionnaire sur DataPrep Pro a été supprimé par l'administrateur.</p>
                        <p>Toutes vos données d'accès ont été retirées de notre système conformément à nos politiques de sécurité.</p>
                    </div>
                    <div class="footer">Équipe DataPrep Pro &bull; Sécurité des Données</div>
                </div>
            </body>
            </html>
            """
            msg.attach(MIMEText(html_body, 'html'))
            self._send(target_email, msg)
            return True, None
        except Exception as e:
            return False, str(e)

    def send_reset_code(self, target_email, code):
        """
        Envoie un code de réinitialisation de mot de passe.
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = f"DataPrep Pro <{self.sender_email}>"
            msg['To'] = target_email
            msg['Subject'] = "DataPrep Pro - Réinitialisation de mot de passe"

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    .container {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px; border-radius: 20px; border: 1px solid #e2e8f0; color: #0A2647; }}
                    .logo {{ font-size: 24px; font-weight: bold; color: #0A2647; text-align: center; margin-bottom: 30px; }}
                    .logo span {{ color: #0061FF; }}
                    .code-box {{ background: #f8fafc; border-radius: 12px; padding: 30px; margin: 24px 0; text-align: center; border: 1px dashed #0061FF; }}
                    .code {{ font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #0061FF; }}
                    .footer {{ margin-top: 40px; font-size: 13px; color: #94a3b8; text-align: center; padding-top: 20px; border-top: 1px solid #f1f5f9; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="logo">Data<span>Prep</span> Pro</div>
                    <div class="content">
                        <h2 style="text-align: center;">Réinitialisation de mot de passe</h2>
                        <p>Vous avez demandé la réinitialisation de votre mot de passe. Utilisez le code confidentiel ci-dessous pour finaliser l'opération :</p>
                        <div class="code-box">
                            <div class="code">{code}</div>
                        </div>
                        <p style="font-size: 14px; color: #64748b;">Ce code est valable pour une durée limitée. Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email.</p>
                    </div>
                    <div class="footer">Équipe DataPrep Pro &bull; Sécurité des comptes</div>
                </div>
            </body>
            </html>
            """
            msg.attach(MIMEText(html_body, 'html'))
            self._send(target_email, msg)
            return True, None
        except Exception as e:
            return False, str(e)

    def _send(self, target_email, msg):
        server = smtplib.SMTP(self.smtp_server, self.smtp_port)
        server.starttls()
        server.login(self.username, self.password)
        text = msg.as_string()
        server.sendmail(self.sender_email, target_email, text)
        server.quit()

    @staticmethod
    def generate_code():
        return "".join([str(random.randint(0, 9)) for _ in range(6)])
