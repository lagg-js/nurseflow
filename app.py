from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, abort
from models import db, Patient, AllergyStatus, VitalSign, NursingNote, NoteType, User, UserRole
from models import ShiftAssignment, ShiftType, ShiftStatus, ShiftSwapRequest
from datetime import datetime, timedelta, date, time
import os
import csv
import io
import random
from functools import wraps
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nurseflow.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get("SECRET_KEY", "chave-apenas-para-desenvolvimento")

db.init_app(app)

# ---------- MAPEAMENTO PARA EXIBIÇÃO COM ACENTUAÇÃO ----------
NOTE_TYPE_LABELS = {
    'evolucao': 'evolução',
    'ocorrencia': 'ocorrência'
}

# ---------- FUNÇÃO PARA CRIAR CONTAS PADRÃO ----------
def create_default_accounts():
    accounts = [
        {'username': 'admin', 'full_name': 'Administrador', 'role': UserRole.MANAGER, 'password': 'admin123'},
        {'username': 'enfermeiro', 'full_name': 'João Silva', 'role': UserRole.NURSE, 'password': '123456'},
        {'username': 'tecnico', 'full_name': 'Maria Santos', 'role': UserRole.TECHNICIAN, 'password': '123456'},
    ]
    
    for acc in accounts:
        if not User.query.filter_by(username=acc['username']).first():
            user = User(username=acc['username'], full_name=acc['full_name'], role=acc['role'])
            user.set_password(acc['password'])
            db.session.add(user)
    
    patient = Patient.query.filter_by(name="Cliente Exemplo").first()
    if not patient:
        patient = Patient(
            name="Cliente Exemplo",
            birth_date=datetime(1990, 1, 1).date(),
            cpf="111.222.333-44",
            phone="(11) 99999-9999",
            emergency_contact="Familiar",
            emergency_phone="(11) 98888-8888",
            allergy_status=AllergyStatus.NONE_KNOWN,
            clinical_info="Paciente saudável",
            created_by="sistema",
            updated_by="sistema"
        )
        db.session.add(patient)
        db.session.commit()
    
    if not User.query.filter_by(username="paciente").first():
        user_paciente = User(
            username="paciente",
            full_name="Cliente Exemplo",
            role=UserRole.PATIENT,
            patient_id=patient.id
        )
        user_paciente.set_password("123456")
        db.session.add(user_paciente)
        db.session.commit()
    else:
        user_paciente = User.query.filter_by(username="paciente").first()
        if not user_paciente.patient_id:
            user_paciente.patient_id = patient.id
            db.session.commit()
    
    # Criar alguns plantões de exemplo para demonstração
    if ShiftAssignment.query.count() == 0:
        admin_user = User.query.filter_by(username="admin").first()
        enfermeiro_user = User.query.filter_by(username="enfermeiro").first()
        tecnico_user = User.query.filter_by(username="tecnico").first()
        
        hoje = date.today()
        start_morning = time(7, 0)
        end_morning = time(13, 0)
        start_afternoon = time(13, 0)
        end_afternoon = time(19, 0)
        
        # Atribuir plantão manhã para enfermeiro
        if enfermeiro_user:
            shift = ShiftAssignment(
                user_id=enfermeiro_user.id,
                shift_type=ShiftType.MORNING,
                shift_date=hoje,
                start_time=start_morning,
                end_time=end_morning,
                status=ShiftStatus.ONGOING,
                assigned_by=admin_user.id if admin_user else None
            )
            db.session.add(shift)
        
        # Atribuir plantão tarde para técnico
        if tecnico_user:
            shift = ShiftAssignment(
                user_id=tecnico_user.id,
                shift_type=ShiftType.AFTERNOON,
                shift_date=hoje,
                start_time=start_afternoon,
                end_time=end_afternoon,
                status=ShiftStatus.SCHEDULED,
                assigned_by=admin_user.id if admin_user else None
            )
            db.session.add(shift)
        
        db.session.commit()

# ---------- DECORADOR DE LOGIN ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Por favor, faça login para acessar esta página.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------- DECORADOR DE AUTORIZAÇÃO POR ROLE ----------
def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Por favor, faça login.", "warning")
                return redirect(url_for('login'))
            user = User.query.get(session['user_id'])
            if not user or user.role.value not in allowed_roles:
                flash("Você não tem permissão para acessar esta página.", "danger")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ---------- FUNÇÃO PARA OBTER STATUS DO PLANTÃO DO USUÁRIO ----------
def get_user_shift_status(user_id):
    hoje = date.today()
    shift = ShiftAssignment.query.filter(
        ShiftAssignment.user_id == user_id,
        ShiftAssignment.shift_date == hoje,
        ShiftAssignment.status.in_([ShiftStatus.SCHEDULED, ShiftStatus.ONGOING])
    ).first()
    if shift:
        return shift.status.value
    return "fora_do_turno"

# ---------- CRIAÇÃO INICIAL ----------
with app.app_context():
    db.create_all()
    create_default_accounts()
    print("✅ Contas padrão criadas:")
    print("   admin / admin123 (gestor)")
    print("   enfermeiro / 123456 (enfermeiro)")
    print("   tecnico / 123456 (técnico)")
    print("   paciente / 123456 (paciente)")
    print("✅ Plantões de exemplo criados (enfermeiro em andamento, técnico agendado)")

# ---------- ROTAS DE AUTENTICAÇÃO ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['full_name'] = user.full_name
            session['role'] = user.role.value if user.role else 'paciente'
            session['patient_id'] = user.patient_id
            flash(f"Bem-vindo, {user.full_name}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Usuário ou senha inválidos.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for('login'))

# ---------- ROTA /SEED (APENAS GESTOR) ----------
@app.route('/seed')
@login_required
@role_required(['gestor'])
def seed_database():
    db.drop_all()
    db.create_all()
    create_default_accounts()

    nomes = ["Ana Paula Souza", "Carlos Eduardo Lima", "Fernanda Oliveira", "José Roberto Alves",
             "Patrícia Costa", "Ricardo Mendes", "Sandra Ferreira", "Thiago Rocha",
             "Vanessa Martins", "Wagner Pires"]
    alergias_opts = [AllergyStatus.NOT_INFORMED, AllergyStatus.NONE_KNOWN, AllergyStatus.HAS_ALLERGIES]
    desc_alergias = ["", "", "Penicilina", "Dipirona", "Morango", "Látex", "Iodo", "Sulfa"]

    for i, nome in enumerate(nomes):
        birth = datetime(1980 + random.randint(0, 20), random.randint(1, 12), random.randint(1, 28))
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

    patients = Patient.query.all()
    for p in patients:
        for _ in range(random.randint(2, 5)):
            v = VitalSign(
                patient_id=p.id,
                record_date=datetime.utcnow() - timedelta(days=random.randint(0, 10), hours=random.randint(0, 23)),
                systolic=random.randint(100, 160),
                diastolic=random.randint(60, 100),
                heart_rate=random.randint(60, 100),
                respiratory_rate=random.randint(12, 24),
                temperature=round(random.uniform(36.0, 38.0), 1),
                oxygen_saturation=random.randint(94, 100),
                pain_scale=random.randint(0, 10),
                notes="Registro de rotina" if random.random() > 0.5 else "",
                created_by="admin"
            )
            db.session.add(v)
        for _ in range(random.randint(1, 3)):
            n = NursingNote(
                patient_id=p.id,
                note_type=random.choice([NoteType.EVOLUTION, NoteType.OCCURRENCE]),
                content=f"Anotação teste {random.randint(1, 100)}: Paciente evoluiu bem durante o plantão." if random.random()>0.5 else "Paciente relatou dor, medicação administrada.",
                created_by="admin"
            )
            db.session.add(n)
    db.session.commit()
    flash("✅ Banco de dados populado com 10 pacientes, sinais vitais e anotações fictícios!", "success")
    return redirect(url_for('index'))

# ---------- HOME ----------
@app.route('/')
@login_required
def index():
    user_role = session.get('role')
    user_patient_id = session.get('patient_id')
    user_id = session.get('user_id')
    shift_status = get_user_shift_status(user_id)
    
    if user_role == 'paciente':
        if not user_patient_id:
            flash("Conta de paciente não vinculada a um paciente.", "warning")
            return render_template('index.html', 
                                 total_patients=0, total_vitals=0, total_notes=0,
                                 allergy_alerts=0, recent_activities=[], days=7,
                                 user_name=session.get('full_name'), user_role=user_role,
                                 shift_status=shift_status)
        patient = Patient.query.get(user_patient_id)
        total_patients = 1
        total_vitals = VitalSign.query.filter_by(patient_id=user_patient_id).count()
        total_notes = NursingNote.query.filter_by(patient_id=user_patient_id).count()
        allergy_alerts = 1 if patient and patient.allergy_status == AllergyStatus.HAS_ALLERGIES else 0
        
        recent_notes = NursingNote.query.filter_by(patient_id=user_patient_id).order_by(NursingNote.created_at.desc()).limit(10).all()
        recent_activities = []
        for note in recent_notes:
            recent_activities.append({
                'time': note.created_at.strftime('%d/%m %H:%M'),
                'user': note.created_by,
                'action': f"registrou {NOTE_TYPE_LABELS.get(note.note_type.value, note.note_type.value)}",
                'target': 'você',
                'patient_id': user_patient_id
            })
        return render_template('index.html', 
                             total_patients=total_patients,
                             total_vitals=total_vitals,
                             total_notes=total_notes,
                             allergy_alerts=allergy_alerts,
                             recent_activities=recent_activities,
                             days=7,
                             user_name=session.get('full_name'),
                             user_role=user_role,
                             shift_status=shift_status)
    
    # Profissionais e gestores
    total_patients = Patient.query.filter_by(is_active=True).count()
    total_vitals = VitalSign.query.count()
    total_notes = NursingNote.query.count()
    allergy_alerts = Patient.query.filter_by(allergy_status=AllergyStatus.HAS_ALLERGIES, is_active=True).count()
    
    days = request.args.get('days', default=7, type=int)
    if days == 0:
        recent_notes = NursingNote.query.order_by(NursingNote.created_at.desc()).limit(10).all()
    else:
        cutoff = datetime.utcnow() - timedelta(days=days)
        recent_notes = NursingNote.query.filter(NursingNote.created_at >= cutoff).order_by(NursingNote.created_at.desc()).limit(10).all()
    
    recent_activities = []
    for note in recent_notes:
        patient = Patient.query.get(note.patient_id)
        patient_name = patient.name if patient else "Paciente removido"
        patient_id = patient.id if patient else None
        note_type_label = NOTE_TYPE_LABELS.get(note.note_type.value, note.note_type.value) if note.note_type else "anotação"
        recent_activities.append({
            'time': note.created_at.strftime('%d/%m %H:%M'),
            'user': note.created_by,
            'action': f"registrou {note_type_label}",
            'target': patient_name,
            'patient_id': patient_id
        })
    
    return render_template('index.html', 
                         total_patients=total_patients,
                         total_vitals=total_vitals,
                         total_notes=total_notes,
                         allergy_alerts=allergy_alerts,
                         recent_activities=recent_activities,
                         days=days,
                         user_name=session.get('full_name'),
                         user_role=user_role,
                         shift_status=shift_status)

# ---------- ROTAS DE PLANTÃO ----------
@app.route('/shift/status', methods=['GET', 'POST'])
@login_required
def my_shift_status():
    user_id = session.get('user_id')
    today = date.today()
    
    # Buscar plantão ativo hoje
    current_shift = ShiftAssignment.query.filter(
        ShiftAssignment.user_id == user_id,
        ShiftAssignment.shift_date == today,
        ShiftAssignment.status.in_([ShiftStatus.SCHEDULED, ShiftStatus.ONGOING])
    ).first()
    
    # Buscar todos os plantões passados (histórico)
    past_shifts = ShiftAssignment.query.filter(
        ShiftAssignment.user_id == user_id,
        ShiftAssignment.shift_date < today
    ).order_by(ShiftAssignment.shift_date.desc()).limit(5).all()
    
    # Buscar próximos plantões agendados
    future_shifts = ShiftAssignment.query.filter(
        ShiftAssignment.user_id == user_id,
        ShiftAssignment.shift_date > today,
        ShiftAssignment.status == ShiftStatus.SCHEDULED
    ).order_by(ShiftAssignment.shift_date.asc()).limit(5).all()
    
    # Verificar solicitações de troca pendentes (para o usuário atual)
    pending_swaps_as_target = ShiftSwapRequest.query.filter(
        ShiftSwapRequest.target_user_id == user_id,
        ShiftSwapRequest.status == ShiftStatus.SCHEDULED
    ).all()
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'start_shift' and current_shift and current_shift.status == ShiftStatus.SCHEDULED:
            current_shift.status = ShiftStatus.ONGOING
            db.session.commit()
            flash("⏰ Plantão iniciado! Bom trabalho!", "success")
            return redirect(url_for('my_shift_status'))
        elif action == 'end_shift' and current_shift and current_shift.status == ShiftStatus.ONGOING:
            current_shift.status = ShiftStatus.COMPLETED
            db.session.commit()
            flash("✅ Plantão finalizado. Relatório de passagem gerado com sucesso!", "success")
            return redirect(url_for('my_shift_status'))
        elif action == 'swap_accept':
            swap_id = request.form.get('swap_id')
            swap = ShiftSwapRequest.query.get(swap_id)
            if swap and swap.target_user_id == user_id and swap.status == ShiftStatus.SCHEDULED:
                # Aceitar troca: atualizar o turno do solicitante
                original_shift = swap.shift_assignment
                # Criar um novo turno para o solicitante com as mesmas informações do turno alvo
                # (simplificado: apenas marcar como trocado e criar novo)
                original_shift.status = ShiftStatus.SWAPPED
                new_shift = ShiftAssignment(
                    user_id=swap.requester_id,
                    shift_type=original_shift.shift_type,
                    shift_date=original_shift.shift_date,
                    start_time=original_shift.start_time,
                    end_time=original_shift.end_time,
                    status=ShiftStatus.SCHEDULED,
                    assigned_by=user_id
                )
                db.session.add(new_shift)
                swap.status = ShiftStatus.COMPLETED
                swap.responded_at = datetime.utcnow()
                swap.responded_by = user_id
                db.session.commit()
                flash("✅ Troca de plantão aprovada com sucesso!", "success")
            return redirect(url_for('my_shift_status'))
        elif action == 'swap_reject':
            swap_id = request.form.get('swap_id')
            swap = ShiftSwapRequest.query.get(swap_id)
            if swap and swap.target_user_id == user_id and swap.status == ShiftStatus.SCHEDULED:
                swap.status = ShiftStatus.MISSED  # Rejeitado
                swap.responded_at = datetime.utcnow()
                swap.responded_by = user_id
                db.session.commit()
                flash("❌ Solicitação de troca rejeitada.", "warning")
            return redirect(url_for('my_shift_status'))
    
    return render_template('shift/status.html', 
                         current_shift=current_shift,
                         past_shifts=past_shifts,
                         future_shifts=future_shifts,
                         pending_swaps=pending_swaps_as_target,
                         user_name=session.get('full_name'),
                         user_role=session.get('role'),
                         shift_status=get_user_shift_status(user_id))

@app.route('/shift/handover')
@login_required
def generate_handover():
    user_id = session.get('user_id')
    user_role = session.get('role')
    if user_role == 'paciente':
        flash("Pacientes não têm acesso a relatórios de plantão.", "danger")
        return redirect(url_for('index'))
    
    # Verifica se o usuário está em plantão (ou é gestor, que pode ver tudo)
    shift_status = get_user_shift_status(user_id)
    if shift_status not in ['em_andamento', 'agendado'] and user_role != 'gestor':
        flash("Você só pode gerar relatório de passagem durante um plantão ativo.", "warning")
        return redirect(url_for('index'))
    
    today = date.today()
    twelve_hours_ago = datetime.utcnow() - timedelta(hours=12)
    
    # 1. Pacientes com alergias ativas
    allergy_patients = Patient.query.filter_by(
        allergy_status=AllergyStatus.HAS_ALLERGIES,
        is_active=True
    ).all()
    
    # 2. Sinais Vitais Alterados nas últimas 12h
    abnormal_vitals = VitalSign.query.filter(
        VitalSign.record_date >= twelve_hours_ago,
        db.or_(
            VitalSign.systolic > 140,
            VitalSign.diastolic > 90,
            VitalSign.temperature > 37.5,
            VitalSign.oxygen_saturation < 95
        )
    ).all()
    
    # Agrupar por paciente
    abnormal_by_patient = {}
    for v in abnormal_vitals:
        if v.patient_id not in abnormal_by_patient:
            abnormal_by_patient[v.patient_id] = []
        abnormal_by_patient[v.patient_id].append(v)
    
    # 3. Anotações críticas (ocorrências) nas últimas 12h
    critical_notes = NursingNote.query.filter(
        NursingNote.created_at >= twelve_hours_ago,
        NursingNote.note_type == NoteType.OCCURRENCE
    ).order_by(NursingNote.created_at.desc()).all()
    
    # Identificar o turno atual (se houver)
    current_shift = ShiftAssignment.query.filter(
        ShiftAssignment.user_id == user_id,
        ShiftAssignment.shift_date == today,
        ShiftAssignment.status == ShiftStatus.ONGOING
    ).first()
    shift_label = current_shift.shift_type.value if current_shift else "Não definido"
    
    handover_data = {
        'generated_by': session.get('full_name'),
        'generated_at': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'shift': shift_label,
        'total_patients': Patient.query.filter_by(is_active=True).count(),
        'allergy_alerts': allergy_patients,
        'abnormal_vitals': abnormal_by_patient,
        'critical_notes': critical_notes,
        'summary': {
            'total_alerts': len(allergy_patients),
            'total_abnormal': len(abnormal_vitals),
            'total_critical_notes': len(critical_notes)
        }
    }
    
    return render_template('shift/handover.html', 
                         report=handover_data,
                         user_name=session.get('full_name'),
                         user_role=user_role)

@app.route('/shift/assign', methods=['GET', 'POST'])
@login_required
@role_required(['gestor'])
def assign_shift():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        shift_type = request.form.get('shift_type')
        shift_date_str = request.form.get('shift_date')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        
        try:
            shift_date = datetime.strptime(shift_date_str, '%Y-%m-%d').date()
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()
        except ValueError:
            flash("Data ou horário inválidos.", "danger")
            return redirect(url_for('assign_shift'))
        
        # Verificar sobreposição de turno (mesmo dia e horário)
        overlapping = ShiftAssignment.query.filter(
            ShiftAssignment.user_id == user_id,
            ShiftAssignment.shift_date == shift_date,
            ShiftAssignment.status != ShiftStatus.COMPLETED
        ).first()
        if overlapping:
            flash("Usuário já possui um plantão neste dia!", "danger")
            return redirect(url_for('assign_shift'))
        
        shift = ShiftAssignment(
            user_id=user_id,
            shift_type=ShiftType(shift_type),
            shift_date=shift_date,
            start_time=start_time,
            end_time=end_time,
            assigned_by=session.get('user_id'),
            status=ShiftStatus.SCHEDULED
        )
        db.session.add(shift)
        db.session.commit()
        flash("Plantão atribuído com sucesso!", "success")
        return redirect(url_for('assign_shift'))
    
    users = User.query.filter(User.role != UserRole.PATIENT).all()
    shifts = ShiftAssignment.query.order_by(ShiftAssignment.shift_date.desc(), ShiftAssignment.start_time).all()
    return render_template('shift/assign.html', 
                         users=users, 
                         shifts=shifts,
                         user_name=session.get('full_name'),
                         user_role=session.get('role'))

@app.route('/shift/swap/request', methods=['POST'])
@login_required
def request_swap():
    requester_id = session.get('user_id')
    target_user_id = request.form.get('target_user_id')
    shift_assignment_id = request.form.get('shift_assignment_id')
    reason = request.form.get('reason', '')
    
    if not target_user_id or not shift_assignment_id:
        flash("Dados incompletos para solicitação de troca.", "danger")
        return redirect(url_for('my_shift_status'))
    
    target_shift = ShiftAssignment.query.get(shift_assignment_id)
    if not target_shift or target_shift.user_id != int(target_user_id):
        flash("Turno inválido ou já alterado.", "danger")
        return redirect(url_for('my_shift_status'))
    
    if target_shift.status != ShiftStatus.SCHEDULED:
        flash("Este plantão não pode ser trocado (já está em andamento ou concluído).", "danger")
        return redirect(url_for('my_shift_status'))
    
    # Verificar se já existe solicitação pendente para este turno
    existing = ShiftSwapRequest.query.filter_by(
        shift_assignment_id=shift_assignment_id,
        status=ShiftStatus.SCHEDULED
    ).first()
    if existing:
        flash("Já existe uma solicitação de troca pendente para este plantão.", "warning")
        return redirect(url_for('my_shift_status'))
    
    swap = ShiftSwapRequest(
        requester_id=requester_id,
        target_user_id=target_user_id,
        shift_assignment_id=shift_assignment_id,
        reason=reason,
        status=ShiftStatus.SCHEDULED
    )
    db.session.add(swap)
    db.session.commit()
    flash("✅ Solicitação de troca enviada para aprovação do colega!", "success")
    return redirect(url_for('my_shift_status'))

@app.route('/shift/swap/cancel/<int:swap_id>', methods=['POST'])
@login_required
def cancel_swap(swap_id):
    swap = ShiftSwapRequest.query.get_or_404(swap_id)
    if swap.requester_id != session.get('user_id'):
        flash("Você não pode cancelar esta solicitação.", "danger")
        return redirect(url_for('my_shift_status'))
    
    if swap.status != ShiftStatus.SCHEDULED:
        flash("Esta solicitação já foi respondida.", "warning")
        return redirect(url_for('my_shift_status'))
    
    swap.status = ShiftStatus.MISSED  # Cancelado
    db.session.commit()
    flash("Solicitação de troca cancelada.", "info")
    return redirect(url_for('my_shift_status'))

# ---------- LISTA DE PACIENTES ----------
@app.route('/patients')
@login_required
@role_required(['gestor', 'enfermeiro', 'tecnico'])
def patient_list():
    search_query = request.args.get('search', '').strip()
    allergy_filter = request.args.get('allergy_status')
    query = Patient.query.filter_by(is_active=True)
    if search_query:
        query = query.filter(Patient.name.ilike(f'%{search_query}%'))
    if allergy_filter == 'com_alergias':
        query = query.filter(Patient.allergy_status == AllergyStatus.HAS_ALLERGIES)
    patients = query.order_by(Patient.name).all()
    return render_template('patients/list.html', 
                         patients=patients,
                         search_query=search_query,
                         allergy_filter=allergy_filter,
                         user_name=session.get('full_name'),
                         user_role=session.get('role'))

# ---------- CRIAR PACIENTE ----------
@app.route('/patient/new', methods=['GET', 'POST'])
@login_required
@role_required(['gestor', 'enfermeiro', 'tecnico'])
def new_patient():
    if request.method == 'POST':
        name = request.form.get('name')
        birth_date_str = request.form.get('birth_date')
        if not name or not birth_date_str:
            flash("Nome e data de nascimento são obrigatórios.", "danger")
            return render_template('patients/form.html', user_name=session.get('full_name'))
        try:
            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Data de nascimento inválida.", "danger")
            return render_template('patients/form.html', user_name=session.get('full_name'))

        cpf = request.form.get('cpf') or None
        phone = request.form.get('phone') or None
        emergency_contact = request.form.get('emergency_contact') or None
        emergency_phone = request.form.get('emergency_phone') or None
        allergy_status_str = request.form.get('allergy_status')
        allergy_status = AllergyStatus(allergy_status_str) if allergy_status_str else AllergyStatus.NOT_INFORMED
        allergies_description = ""
        if allergy_status == AllergyStatus.HAS_ALLERGIES:
            allergies_description = request.form.get('allergies_description', '')
        clinical_info = request.form.get('clinical_info', '')
        
        patient = Patient(
            name=name, birth_date=birth_date, cpf=cpf, phone=phone,
            emergency_contact=emergency_contact, emergency_phone=emergency_phone,
            allergy_status=allergy_status, allergies_description=allergies_description,
            clinical_info=clinical_info,
            created_by=session.get('full_name', 'sistema'),
            updated_by=session.get('full_name', 'sistema')
        )
        db.session.add(patient)
        db.session.commit()
        flash(f"Paciente {patient.name} cadastrado com sucesso!", "success")
        return redirect(url_for('patient_list'))
    return render_template('patients/form.html', user_name=session.get('full_name'))

# ---------- EDITAR PACIENTE ----------
@app.route('/patient/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['gestor', 'enfermeiro', 'tecnico'])
def edit_patient(id):
    patient = Patient.query.get_or_404(id)
    if request.method == 'POST':
        patient.name = request.form.get('name')
        try:
            patient.birth_date = datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date()
        except:
            flash("Data de nascimento inválida.", "danger")
            return render_template('patients/edit.html', patient=patient, user_name=session.get('full_name'))
        patient.cpf = request.form.get('cpf') or None
        patient.phone = request.form.get('phone') or None
        patient.emergency_contact = request.form.get('emergency_contact') or None
        patient.emergency_phone = request.form.get('emergency_phone') or None
        allergy_status_str = request.form.get('allergy_status')
        patient.allergy_status = AllergyStatus(allergy_status_str) if allergy_status_str else AllergyStatus.NOT_INFORMED
        patient.allergies_description = request.form.get('allergies_description', '') if patient.allergy_status == AllergyStatus.HAS_ALLERGIES else ''
        patient.clinical_info = request.form.get('clinical_info', '')
        patient.updated_by = session.get('full_name', 'sistema')
        db.session.commit()
        flash(f"Dados de {patient.name} atualizados com sucesso!", "success")
        return redirect(url_for('patient_detail', id=patient.id))
    return render_template('patients/edit.html', patient=patient, user_name=session.get('full_name'))

# ---------- CONFIRMAR EXCLUSÃO (APENAS GESTOR) ----------
@app.route('/patient/<int:id>/confirm_delete')
@login_required
@role_required(['gestor'])
def confirm_delete_patient(id):
    patient = Patient.query.get_or_404(id)
    return render_template('patients/confirm_delete.html', patient=patient, user_name=session.get('full_name'))

# ---------- EXCLUIR PACIENTE (APENAS GESTOR) ----------
@app.route('/patient/<int:id>/delete', methods=['POST'])
@login_required
@role_required(['gestor'])
def delete_patient(id):
    patient = Patient.query.get_or_404(id)
    patient.is_active = False
    patient.updated_by = session.get('full_name', 'sistema')
    db.session.commit()
    flash(f"Paciente {patient.name} foi desativado.", "warning")
    return redirect(url_for('patient_list'))

# ---------- DETALHES DO PACIENTE ----------
@app.route('/patient/<int:id>')
@login_required
def patient_detail(id):
    user_role = session.get('role')
    user_patient_id = session.get('patient_id')
    if user_role == 'paciente':
        if user_patient_id != id:
            flash("Você só pode acessar seus próprios dados.", "danger")
            return redirect(url_for('index'))
    patient = Patient.query.get_or_404(id)
    vital_signs = VitalSign.query.filter_by(patient_id=id).order_by(VitalSign.record_date.desc()).all()
    nursing_notes = NursingNote.query.filter_by(patient_id=id).order_by(NursingNote.created_at.desc()).all()
    return render_template('patients/detail.html', 
                         patient=patient,
                         vital_signs=vital_signs,
                         nursing_notes=nursing_notes,
                         user_name=session.get('full_name'),
                         user_role=user_role)

# ---------- ADICIONAR SINAL VITAL ----------
@app.route('/patient/<int:id>/vital/add', methods=['POST'])
@login_required
@role_required(['gestor', 'enfermeiro', 'tecnico'])
def add_vital_sign(id):
    patient = Patient.query.get_or_404(id)
    if not request.form.get('systolic') or not request.form.get('diastolic'):
        flash("Pressão sistólica e diastólica são obrigatórias.", "danger")
        return redirect(url_for('patient_detail', id=id))
    vital = VitalSign(
        patient_id=id,
        systolic=request.form.get('systolic', type=int),
        diastolic=request.form.get('diastolic', type=int),
        heart_rate=request.form.get('heart_rate', type=int),
        respiratory_rate=request.form.get('respiratory_rate', type=int),
        temperature=request.form.get('temperature', type=float),
        oxygen_saturation=request.form.get('oxygen_saturation', type=int),
        pain_scale=request.form.get('pain_scale', type=int),
        notes=request.form.get('notes', ''),
        created_by=session.get('full_name', 'sistema')
    )
    db.session.add(vital)
    db.session.commit()
    flash("Sinais vitais registrados com sucesso!", "success")
    return redirect(url_for('patient_detail', id=id))

# ---------- DELETAR SINAL VITAL ----------
@app.route('/vital/<int:id>/delete', methods=['POST'])
@login_required
@role_required(['gestor', 'enfermeiro', 'tecnico'])
def delete_vital_sign(id):
    vital = VitalSign.query.get_or_404(id)
    patient_id = vital.patient_id
    db.session.delete(vital)
    db.session.commit()
    flash("Registro de sinal vital removido.", "warning")
    return redirect(url_for('patient_detail', id=patient_id))

# ---------- ADICIONAR ANOTAÇÃO ----------
@app.route('/patient/<int:id>/note/add', methods=['POST'])
@login_required
@role_required(['gestor', 'enfermeiro', 'tecnico'])
def add_nursing_note(id):
    patient = Patient.query.get_or_404(id)
    content = request.form.get('content', '').strip()
    if not content:
        flash("O conteúdo da anotação não pode estar vazio.", "danger")
        return redirect(url_for('patient_detail', id=id))
    note_type_str = request.form.get('note_type')
    note_type = NoteType(note_type_str) if note_type_str else NoteType.EVOLUTION
    note = NursingNote(
        patient_id=id,
        note_type=note_type,
        content=content,
        created_by=session.get('full_name', 'sistema')
    )
    db.session.add(note)
    db.session.commit()
    flash("Anotação registrada com sucesso!", "success")
    return redirect(url_for('patient_detail', id=id))

# ---------- DELETAR ANOTAÇÃO ----------
@app.route('/note/<int:id>/delete', methods=['POST'])
@login_required
@role_required(['gestor', 'enfermeiro', 'tecnico'])
def delete_nursing_note(id):
    note = NursingNote.query.get_or_404(id)
    patient_id = note.patient_id
    db.session.delete(note)
    db.session.commit()
    flash("Anotação removida.", "warning")
    return redirect(url_for('patient_detail', id=patient_id))

# ---------- HISTÓRICO DE SINAIS VITAIS ----------
@app.route('/vitals')
@login_required
@role_required(['gestor', 'enfermeiro', 'tecnico'])
def vitals_list():
    filter_patient = request.args.get('patient_id', type=int)
    if filter_patient:
        vitals = VitalSign.query.filter_by(patient_id=filter_patient).order_by(VitalSign.record_date.desc()).all()
    else:
        vitals = VitalSign.query.order_by(VitalSign.record_date.desc()).all()
    patients = Patient.query.filter_by(is_active=True).order_by(Patient.name).all()
    return render_template('vitals/list.html', 
                         vitals=vitals, 
                         patients=patients,
                         filter_patient=filter_patient,
                         user_name=session.get('full_name'))

# ---------- HISTÓRICO DE ANOTAÇÕES ----------
@app.route('/notes')
@login_required
@role_required(['gestor', 'enfermeiro', 'tecnico'])
def notes_list():
    filter_patient = request.args.get('patient_id', type=int)
    if filter_patient:
        notes = NursingNote.query.filter_by(patient_id=filter_patient).order_by(NursingNote.created_at.desc()).all()
    else:
        notes = NursingNote.query.order_by(NursingNote.created_at.desc()).all()
    patients = Patient.query.filter_by(is_active=True).order_by(Patient.name).all()
    return render_template('notes/list.html', 
                         notes=notes, 
                         patients=patients,
                         filter_patient=filter_patient,
                         user_name=session.get('full_name'))

# ---------- EXPORTAR CSV (APENAS GESTOR) ----------
@app.route('/patient/<int:id>/vitals/export')
@login_required
@role_required(['gestor'])
def export_vitals_csv(id):
    patient = Patient.query.get_or_404(id)
    vitals = VitalSign.query.filter_by(patient_id=id).order_by(VitalSign.record_date.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Data/Hora', 'PA (sist/dias)', 'FC (bpm)', 'FR (irpm)', 'Temp (°C)', 'SpO₂ (%)', 'Dor (0-10)', 'Observações', 'Registrado por'])
    for v in vitals:
        writer.writerow([
            v.record_date.strftime('%d/%m/%Y %H:%M') if v.record_date else '',
            f"{v.systolic}/{v.diastolic}" if v.systolic and v.diastolic else '',
            v.heart_rate or '',
            v.respiratory_rate or '',
            v.temperature or '',
            v.oxygen_saturation or '',
            v.pain_scale or '',
            v.notes or '',
            v.created_by or ''
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=vitals_{patient.name.replace(' ', '_')}.csv"}
    )

if __name__ == '__main__':
    app.run(debug=True)