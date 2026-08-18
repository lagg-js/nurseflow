# 🏥 NurseFlow

Sistema de apoio à organização e acompanhamento da assistência de enfermagem, com gestão de plantões e relatório de passagem de turno.

## 🔗 Link para o WebApp
👉 **[Acesse o NurseFlow](https://nurseflow.onrender.com)**

## 👥 Contas para Teste

| Usuário   | Senha    | Perfil     |
|-----------|----------|------------|
| admin     | admin123 | 👑 Gestor  |
| enfermeiro| 123456   | 👨‍⚕️ Enfermeiro |
| tecnico   | 123456   | 🩺 Técnico |
| paciente  | 123456   | 🧑‍💼 Paciente |

## 🧠 Funcionalidades

- ✅ Cadastro, edição e desativação de pacientes
- ✅ Sinais vitais com alertas de alteração
- ✅ Anotações de enfermagem (Evolução / Ocorrência)
- ✅ Controle de Plantão com status (Em andamento / Agendado / Fora do turno)
- ✅ Relatório de Passagem de Plantão (Shift Handover)
- ✅ Perfis com restrições de acesso (Gestor, Enfermeiro, Técnico, Paciente)
- ✅ Rastreabilidade de alterações (quem criou/editou)
- ✅ Exportação de sinais vitais para CSV
- ✅ Interface responsiva com menu lateral

## 🚀 Tecnologias

- Python 3 + Flask
- SQLite + SQLAlchemy
- Bootstrap 5 + FontAwesome
- Gunicorn (servidor de produção)

## 📦 Como rodar localmente

```bash
git clone https://github.com/SEU-USUARIO/nurseflow.git
cd nurseflow
pip install -r requirements.txt
python app.py
