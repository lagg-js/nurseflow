# seed.py
from app import app, db
from models import User, Patient, VitalSign, NursingNote, AllergyStatus, NoteType, UserRole
from datetime import datetime, timedelta
import random

def seed_database():
    with app.app_context():
        # Limpa tudo
        db.drop_all()
        db.create_all()

        # Usuários
        admin = User(username="admin", full_name="Administrador", role=UserRole.MANAGER)
        admin.set_password("admin123")
        enfermeiro = User(username="enfermeiro", full_name="João Silva", role=UserRole.NURSE)
        enfermeiro.set_password("123456")
        tecnico = User(username="tecnico", full_name="Maria Santos", role=UserRole.TECHNICIAN)
        tecnico.set_password("123456")
        db.session.add_all([admin, enfermeiro, tecnico])
        db.session.commit()

        # Pacientes (10)
        nomes = ["Ana Paula Souza", "Carlos Eduardo Lima", "Fernanda Oliveira", "José Roberto Alves",
                 "Patrícia Costa", "Ricardo Mendes", "Sandra Ferreira", "Thiago Rocha",
                 "Vanessa Martins", "Wagner Pires"]
        alergias_opts = [AllergyStatus.NOT_INFORMED, AllergyStatus.NONE_KNOWN, AllergyStatus.HAS_ALLERGIES]
        desc_alergias = ["", "", "Penicilina", "Dipirona", "Morango", "Látex", "Iodo", "Sulfa"]

        for i, nome in enumerate(nomes):
            birth = datetime(1980 + random.randint(0, 20), random.randint(1,12), random.randint(1,28))
            allergy = random.choice(alergias_opts)
            p = Patient(
                name=nome,
                birth_date=birth,
                cpf=f"{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(0,9):02d}",
                phone=f"({random.randint(11,99)}) 9{random.randint(1000,9999)}-{random.randint(1000,9999)}",
                emergency_contact=f"Familiar {random.randint(1,5)}",
                emergency_phone=f"({random.randint(11,99)}) 9{random.randint(1000,9999)}-{random.randint(1000,9999)}",
                allergy_status=allergy,
                allergies_description=random.choice(desc_alergias) if allergy == AllergyStatus.HAS_ALLERGIES else "",
                clinical_info=f"Doença crônica: {'Hipertensão' if i%2==0 else 'Diabetes' if i%3==0 else 'Nenhuma'}",
                created_by="admin",
                updated_by="admin"
            )
            db.session.add(p)
        db.session.commit()

        # Para cada paciente, criar alguns sinais e anotações
        patients = Patient.query.all()
        for p in patients:
            for _ in range(random.randint(2,5)):
                v = VitalSign(
                    patient_id=p.id,
                    record_date=datetime.utcnow() - timedelta(days=random.randint(0,10), hours=random.randint(0,23)),
                    systolic=random.randint(100,160),
                    diastolic=random.randint(60,100),
                    heart_rate=random.randint(60,100),
                    respiratory_rate=random.randint(12,24),
                    temperature=round(random.uniform(36.0,38.0),1),
                    oxygen_saturation=random.randint(94,100),
                    pain_scale=random.randint(0,10),
                    notes="Registro de rotina" if random.random()>0.5 else "",
                    created_by="admin"
                )
                db.session.add(v)
            for _ in range(random.randint(1,3)):
                n = NursingNote(
                    patient_id=p.id,
                    note_type=random.choice([NoteType.EVOLUTION, NoteType.OCCURRENCE]),
                    content=f"Anotação teste {random.randint(1,100)}",
                    created_by="admin"
                )
                db.session.add(n)
        db.session.commit()
        print("✅ Banco de dados populado com dados fictícios!")