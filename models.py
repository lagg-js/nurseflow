from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, time
import enum
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ---------- ENUMS ----------
class AllergyStatus(enum.Enum):
    NOT_INFORMED = "nao_informado"
    NONE_KNOWN = "sem_alergias_conhecidas"
    HAS_ALLERGIES = "com_alergias"

class NoteType(enum.Enum):
    EVOLUTION = "evolucao"
    OCCURRENCE = "ocorrencia"

class UserRole(enum.Enum):
    MANAGER = "gestor"
    NURSE = "enfermeiro"
    TECHNICIAN = "tecnico"
    PATIENT = "paciente"

# ---------- GESTÃO DE PLANTÃO / TURNOS ----------
class ShiftType(enum.Enum):
    MORNING = "manha"           # 07:00 - 13:00
    AFTERNOON = "tarde"         # 13:00 - 19:00
    NIGHT = "noite"             # 19:00 - 07:00
    TWELVE_THIRTY_SIX = "12x36" # 12h trabalho / 36h descanso

class ShiftStatus(enum.Enum):
    SCHEDULED = "agendado"
    ONGOING = "em_andamento"
    COMPLETED = "concluido"
    MISSED = "faltou"
    SWAPPED = "trocado"

class ShiftAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    shift_type = db.Column(db.Enum(ShiftType), nullable=False)
    shift_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.Enum(ShiftStatus), default=ShiftStatus.SCHEDULED)
    
    assigned_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', foreign_keys=[user_id])
    assigner = db.relationship('User', foreign_keys=[assigned_by])

    def __repr__(self):
        return f"<ShiftAssignment {self.user.username} {self.shift_type.value} {self.shift_date}>"

class ShiftSwapRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    shift_assignment_id = db.Column(db.Integer, db.ForeignKey('shift_assignment.id'), nullable=False)
    
    status = db.Column(db.Enum(ShiftStatus), default=ShiftStatus.SCHEDULED)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)
    responded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    requester = db.relationship('User', foreign_keys=[requester_id])
    target_user = db.relationship('User', foreign_keys=[target_user_id])
    shift_assignment = db.relationship('ShiftAssignment')
    responder = db.relationship('User', foreign_keys=[responded_by])

    def __repr__(self):
        return f"<ShiftSwapRequest {self.requester.username} -> {self.target_user.username}>"

# ---------- USUÁRIO ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.PATIENT)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=True)
    patient = db.relationship('Patient', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} ({self.role.value})>"

# ---------- PACIENTE ----------
class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    cpf = db.Column(db.String(14), unique=True)
    phone = db.Column(db.String(20))
    emergency_contact = db.Column(db.String(150))
    emergency_phone = db.Column(db.String(20))
    
    allergy_status = db.Column(db.Enum(AllergyStatus), default=AllergyStatus.NOT_INFORMED)
    allergies_description = db.Column(db.Text, default="")
    clinical_info = db.Column(db.Text, default="")
    
    created_by = db.Column(db.String(100), default="sistema")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_by = db.Column(db.String(100), default="sistema")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    vital_signs = db.relationship('VitalSign', backref='patient', lazy=True, cascade="all, delete-orphan")
    nursing_notes = db.relationship('NursingNote', backref='patient', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Patient {self.name}>"

# ---------- SINAIS VITAIS ----------
class VitalSign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    record_date = db.Column(db.DateTime, default=datetime.utcnow)
    systolic = db.Column(db.Integer)
    diastolic = db.Column(db.Integer)
    heart_rate = db.Column(db.Integer)
    respiratory_rate = db.Column(db.Integer)
    temperature = db.Column(db.Float)
    oxygen_saturation = db.Column(db.Integer)
    pain_scale = db.Column(db.Integer)
    notes = db.Column(db.Text)
    created_by = db.Column(db.String(100), default="sistema")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<VitalSign patient={self.patient_id} at {self.record_date}>"

# ---------- ANOTAÇÕES ----------
class NursingNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    note_type = db.Column(db.Enum(NoteType), default=NoteType.EVOLUTION)
    content = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(100), default="sistema")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<NursingNote {self.note_type.value} patient={self.patient_id}>"