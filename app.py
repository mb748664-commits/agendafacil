from flask import Flask, render_template, request, redirect, session
from banco import conectar_banco

app = Flask(__name__)

app.secret_key = "agendafacil123"

# ==========================================
# PAGINA INICIAL
# ==========================================

@app.route("/")
def inicio():
    return render_template("index.html")


# ==========================================
# CADASTRO DO USUARIO
# ==========================================

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():

    if request.method == "POST":

        nome = request.form["nome"]
        email = request.form["email"]
        telefone = request.form["telefone"]
        senha = request.form["senha"]

        conexao = conectar_banco()
        cursor = conexao.cursor()

        sql = """
        INSERT INTO usuarios
        (nome, email, telefone, senha)
        VALUES (%s, %s, %s, %s)
        """

        cursor.execute(
            sql,
            (nome, email, telefone, senha)
        )

        conexao.commit()

        cursor.close()
        conexao.close()

        return "Cadastro realizado com sucesso!"

    return render_template("cadastro.html")


# ==========================================
# LOGIN DO USUARIO
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        senha = request.form["senha"]

        conexao = conectar_banco()
        cursor = conexao.cursor()

        sql = """
        SELECT id, nome, email
        FROM usuarios
        WHERE email = %s
        AND senha = %s
        """

        cursor.execute(
            sql,
            (email, senha)
        )

        usuario = cursor.fetchone()

        cursor.close()
        conexao.close()

        if usuario:

            session["usuario_id"] = usuario[0]
            session["usuario_nome"] = usuario[1]

            return redirect("/usuario")

        return "E-mail ou senha incorretos!"

    return render_template("login.html")


# ==========================================
# AREA DO USUARIO
# ==========================================

@app.route("/usuario")
def usuario():

    if "usuario_id" not in session:
        return redirect("/login")

    usuario_id = session["usuario_id"]
    nome = session["usuario_nome"]

    conexao = conectar_banco()
    cursor = conexao.cursor()

    sql = """
    SELECT
        agendamentos.id,
        estabelecimentos.nome,
        servicos.nome,
        agendamentos.data_agendamento,
        agendamentos.horario,
        agendamentos.status
    FROM agendamentos

    INNER JOIN servicos
        ON agendamentos.servico_id = servicos.id

    INNER JOIN estabelecimentos
        ON servicos.estabelecimento_id = estabelecimentos.id

    WHERE agendamentos.usuario_id = %s

    ORDER BY
        agendamentos.data_agendamento,
        agendamentos.horario
    """

    cursor.execute(
        sql,
        (usuario_id,)
    )

    agendamentos = cursor.fetchall()

    cursor.close()
    conexao.close()

    return render_template(
        "usuario.html",
        nome=nome,
        agendamentos=agendamentos
    )


# ==========================================
# LISTA DE ESTABELECIMENTOS
# ==========================================

@app.route("/estabelecimentos")
def estabelecimentos():

    if "usuario_id" not in session:
        return redirect("/login")

    conexao = conectar_banco()
    cursor = conexao.cursor()

    sql = """
    SELECT
        id,
        nome,
        email,
        telefone,
        endereco,
        descricao
    FROM estabelecimentos
    """

    cursor.execute(sql)

    lista_estabelecimentos = cursor.fetchall()

    cursor.close()
    conexao.close()

    return render_template(
        "estabelecimentos.html",
        estabelecimentos=lista_estabelecimentos
    )


# ==========================================
# SERVICOS DO ESTABELECIMENTO
# ==========================================

@app.route("/servicos-estabelecimento/<int:id_estabelecimento>")
def servicos_estabelecimento(id_estabelecimento):

    if "usuario_id" not in session:
        return redirect("/login")

    conexao = conectar_banco()
    cursor = conexao.cursor()

    sql = """
    SELECT
        id,
        nome,
        email,
        telefone,
        endereco,
        descricao
    FROM estabelecimentos
    WHERE id = %s
    """

    cursor.execute(
        sql,
        (id_estabelecimento,)
    )

    estabelecimento = cursor.fetchone()

    if estabelecimento is None:

        cursor.close()
        conexao.close()

        return "Estabelecimento não encontrado!"

    sql = """
    SELECT
        id,
        nome,
        descricao,
        duracao
    FROM servicos
    WHERE estabelecimento_id = %s
    """

    cursor.execute(
        sql,
        (id_estabelecimento,)
    )

    servicos = cursor.fetchall()

    cursor.close()
    conexao.close()

    return render_template(
        "servicos_estabelecimento.html",
        estabelecimento=estabelecimento,
        servicos=servicos
    )


# ==========================================
# AGENDAR SERVICO
# ==========================================

@app.route("/agendar/<int:id_servico>", methods=["GET", "POST"])
def agendar(id_servico):

    if "usuario_id" not in session:
        return redirect("/login")

    conexao = conectar_banco()
    cursor = conexao.cursor()

    # Buscar serviço
    cursor.execute("""
        SELECT id, nome, descricao, duracao, estabelecimento_id
        FROM servicos
        WHERE id = %s
    """, (id_servico,))

    servico = cursor.fetchone()

    if servico is None:
        cursor.close()
        conexao.close()
        return "Serviço não encontrado!"

    # Buscar estabelecimento
    cursor.execute("""
        SELECT id, nome
        FROM estabelecimentos
        WHERE id = %s
    """, (servico[4],))

    estabelecimento = cursor.fetchone()

    # Horários disponíveis
    horarios = [
        "09:00", "10:00", "11:00", "12:00", "13:00",
        "14:00", "15:00", "16:00", "17:00", "18:00"
    ]

    # ==================================================
    # CONFIRMAR AGENDAMENTO
    # ==================================================

    if request.method == "POST":

        data = request.form.get("data")
        horario = request.form.get("horario")

        if not data or not horario:
            cursor.close()
            conexao.close()
            return "Data e horário são obrigatórios."

        # Verificar horário ocupado no estabelecimento
        cursor.execute("""
            SELECT agendamentos.id
            FROM agendamentos
            INNER JOIN servicos
                ON agendamentos.servico_id = servicos.id
            WHERE servicos.estabelecimento_id = %s
              AND agendamentos.data_agendamento = %s
              AND agendamentos.horario = %s
              AND agendamentos.status != 'cancelado'
        """, (servico[4], data, horario))

        ocupado = cursor.fetchone()

        if ocupado:
            cursor.close()
            conexao.close()

            return render_template(
                "agendar.html",
                servico=servico,
                estabelecimento=estabelecimento,
                horarios=horarios,
                horarios_ocupados=[horario],
                data_selecionada=data,
                horario_ocupado=horario
            )

        # Criar o agendamento
        cursor.execute("""
            INSERT INTO agendamentos
            (
                usuario_id,
                servico_id,
                data_agendamento,
                horario,
                status
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            session["usuario_id"],
            id_servico,
            data,
            horario,
            "pendente"
        ))

        conexao.commit()

        cursor.close()
        conexao.close()

        return redirect("/usuario")

    # ==================================================
    # MOSTRAR HORÁRIOS PARA A DATA ESCOLHIDA
    # ==================================================

    data_selecionada = request.args.get("data")
    horarios_ocupados = []

    if data_selecionada:

        cursor.execute("""
            SELECT agendamentos.horario
            FROM agendamentos
            INNER JOIN servicos
                ON agendamentos.servico_id = servicos.id
            WHERE servicos.estabelecimento_id = %s
              AND agendamentos.data_agendamento = %s
              AND agendamentos.status != 'cancelado'
        """, (servico[4], data_selecionada))

        for resultado in cursor.fetchall():
            valor = resultado[0]
            horario_texto = str(valor)[:5]
            horarios_ocupados.append(horario_texto)

    cursor.close()
    conexao.close()

    return render_template(
        "agendar.html",
        servico=servico,
        estabelecimento=estabelecimento,
        horarios=horarios,
        horarios_ocupados=horarios_ocupados,
        data_selecionada=data_selecionada
    )


# ==========================================
# CADASTRO DO ESTABELECIMENTO
# ==========================================

@app.route(
    "/cadastro-estabelecimento",
    methods=["GET", "POST"]
)
def cadastro_estabelecimento():

    if request.method == "POST":

        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]
        telefone = request.form["telefone"]
        endereco = request.form["endereco"]
        descricao = request.form["descricao"]

        conexao = conectar_banco()
        cursor = conexao.cursor()

        sql = """
        INSERT INTO estabelecimentos
        (
            nome,
            email,
            senha,
            telefone,
            endereco,
            descricao
        )

        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        """

        cursor.execute(
            sql,
            (
                nome,
                email,
                senha,
                telefone,
                endereco,
                descricao
            )
        )

        conexao.commit()

        cursor.close()
        conexao.close()

        return "Estabelecimento cadastrado com sucesso!"

    return render_template(
        "cadastro_estabelecimento.html"
    )


# ==========================================
# LOGIN DO ESTABELECIMENTO
# ==========================================

@app.route(
    "/login-estabelecimento",
    methods=["GET", "POST"]
)
def login_estabelecimento():

    if request.method == "POST":

        email = request.form["email"]
        senha = request.form["senha"]

        conexao = conectar_banco()
        cursor = conexao.cursor()

        sql = """
        SELECT
            id,
            nome,
            email
        FROM estabelecimentos

        WHERE email = %s
        AND senha = %s
        """

        cursor.execute(
            sql,
            (email, senha)
        )

        estabelecimento = cursor.fetchone()

        cursor.close()
        conexao.close()

        if estabelecimento:

            session["estabelecimento_id"] = estabelecimento[0]

            session["estabelecimento_nome"] = estabelecimento[1]

            return redirect("/estabelecimento")

        return "E-mail ou senha incorretos!"

    return render_template(
        "login_estabelecimento.html"
    )


# ==========================================
# AREA DO ESTABELECIMENTO
# ==========================================

@app.route("/estabelecimento")
def estabelecimento():

    if "estabelecimento_id" not in session:
        return redirect("/login-estabelecimento")

    estabelecimento_id = session["estabelecimento_id"]

    nome = session["estabelecimento_nome"]

    conexao = conectar_banco()
    cursor = conexao.cursor()

    sql = """
    SELECT
        agendamentos.id,
        usuarios.nome,
        servicos.nome,
        agendamentos.data_agendamento,
        agendamentos.horario,
        agendamentos.status

    FROM agendamentos

    INNER JOIN usuarios
        ON agendamentos.usuario_id = usuarios.id

    INNER JOIN servicos
        ON agendamentos.servico_id = servicos.id

    WHERE servicos.estabelecimento_id = %s

    ORDER BY
        agendamentos.data_agendamento,
        agendamentos.horario
    """

    cursor.execute(
        sql,
        (estabelecimento_id,)
    )

    agendamentos = cursor.fetchall()

    cursor.close()
    conexao.close()

    return render_template(
        "estabelecimento.html",
        nome=nome,
        agendamentos=agendamentos
    )


# ==========================================
# CONFIRMAR AGENDAMENTO
# ==========================================

@app.route(
    "/confirmar-agendamento/<int:id_agendamento>",
    methods=["POST"]
)
def confirmar_agendamento(id_agendamento):

    if "estabelecimento_id" not in session:
        return redirect("/login-estabelecimento")

    estabelecimento_id = session["estabelecimento_id"]

    conexao = conectar_banco()
    cursor = conexao.cursor()

    sql = """
    UPDATE agendamentos

    INNER JOIN servicos
        ON agendamentos.servico_id = servicos.id

    SET agendamentos.status = 'confirmado'

    WHERE agendamentos.id = %s

    AND servicos.estabelecimento_id = %s
    """

    cursor.execute(
        sql,
        (
            id_agendamento,
            estabelecimento_id
        )
    )

    conexao.commit()

    cursor.close()
    conexao.close()

    return redirect("/estabelecimento")


# ==========================================
# CANCELAR AGENDAMENTO
# ==========================================

@app.route(
    "/cancelar-agendamento/<int:id_agendamento>",
    methods=["POST"]
)
def cancelar_agendamento(id_agendamento):

    if "estabelecimento_id" not in session:
        return redirect("/login-estabelecimento")

    estabelecimento_id = session["estabelecimento_id"]

    conexao = conectar_banco()
    cursor = conexao.cursor()

    sql = """
    UPDATE agendamentos

    INNER JOIN servicos
        ON agendamentos.servico_id = servicos.id

    SET agendamentos.status = 'cancelado'

    WHERE agendamentos.id = %s

    AND servicos.estabelecimento_id = %s
    """

    cursor.execute(
        sql,
        (
            id_agendamento,
            estabelecimento_id
        )
    )

    conexao.commit()

    cursor.close()
    conexao.close()

    return redirect("/estabelecimento")


# ==========================================
# MEUS SERVICOS
# ==========================================

@app.route(
    "/servicos",
    methods=["GET", "POST"]
)
def servicos():

    if "estabelecimento_id" not in session:
        return redirect("/login-estabelecimento")

    estabelecimento_id = session["estabelecimento_id"]

    conexao = conectar_banco()
    cursor = conexao.cursor()


    # ==========================================
    # CADASTRAR SERVICO
    # ==========================================

    if request.method == "POST":

        nome = request.form["nome"]

        descricao = request.form["descricao"]

        duracao = request.form["duracao"]

        sql = """
        INSERT INTO servicos
        (
            estabelecimento_id,
            nome,
            descricao,
            duracao
        )

        VALUES
        (
            %s,
            %s,
            %s,
            %s
        )
        """

        cursor.execute(
            sql,
            (
                estabelecimento_id,
                nome,
                descricao,
                duracao
            )
        )

        conexao.commit()


    # ==========================================
    # LISTAR SERVICOS
    # ==========================================

    sql = """
    SELECT
        id,
        nome,
        descricao,
        duracao

    FROM servicos

    WHERE estabelecimento_id = %s
    """

    cursor.execute(
        sql,
        (estabelecimento_id,)
    )

    lista_servicos = cursor.fetchall()

    cursor.close()
    conexao.close()

    return render_template(
        "servicos.html",
        servicos=lista_servicos
    )


# ==========================================
# EDITAR SERVICO
# ==========================================

@app.route("/editar-servico/<int:id_servico>", methods=["GET", "POST"])
def editar_servico(id_servico):

    if "estabelecimento_id" not in session:
        return redirect("/login-estabelecimento")

    estabelecimento_id = session["estabelecimento_id"]

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, descricao, duracao
        FROM servicos
        WHERE id = %s
        AND estabelecimento_id = %s
    """, (id_servico, estabelecimento_id))

    servico = cursor.fetchone()

    if servico is None:
        cursor.close()
        conexao.close()
        return "Serviço não encontrado!"

    if request.method == "POST":

        nome = request.form["nome"]
        descricao = request.form["descricao"]
        duracao = request.form["duracao"]

        cursor.execute("""
            UPDATE servicos
            SET nome = %s,
                descricao = %s,
                duracao = %s
            WHERE id = %s
            AND estabelecimento_id = %s
        """, (nome, descricao, duracao, id_servico, estabelecimento_id))

        conexao.commit()
        cursor.close()
        conexao.close()

        return redirect("/servicos")

    cursor.close()
    conexao.close()

    return render_template("editar_servico.html", servico=servico)


# ==========================================
# EXCLUIR SERVICO
# ==========================================

@app.route("/excluir-servico/<int:id_servico>", methods=["POST"])
def excluir_servico(id_servico):

    if "estabelecimento_id" not in session:
        return redirect("/login-estabelecimento")

    estabelecimento_id = session["estabelecimento_id"]

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id
        FROM agendamentos
        WHERE servico_id = %s
        LIMIT 1
    """, (id_servico,))

    agendamento = cursor.fetchone()

    if agendamento:
        cursor.close()
        conexao.close()
        return """
        <h2>Não é possível excluir este serviço.</h2>
        <p>Este serviço possui agendamentos cadastrados.</p>
        <p>Cancele ou remova os agendamentos relacionados antes de excluir o serviço.</p>
        <a href="/servicos">Voltar para Meus Serviços</a>
        """

    cursor.execute("""
        DELETE FROM servicos
        WHERE id = %s
        AND estabelecimento_id = %s
    """, (id_servico, estabelecimento_id))

    conexao.commit()
    cursor.close()
    conexao.close()

    return redirect("/servicos")


# ==========================================
# CANCELAR AGENDAMENTO PELO USUARIO
# ==========================================

@app.route(
    "/cancelar-meu-agendamento/<int:id_agendamento>",
    methods=["POST"]
)
def cancelar_meu_agendamento(id_agendamento):

    if "usuario_id" not in session:
        return redirect("/login")

    usuario_id = session["usuario_id"]

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE agendamentos
        SET status = 'cancelado'
        WHERE id = %s
        AND usuario_id = %s
        AND status != 'cancelado'
    """, (id_agendamento, usuario_id))

    conexao.commit()

    cursor.close()
    conexao.close()

    return redirect("/usuario")


# ==========================================
# SAIR
# ==========================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# ==========================================
# INICIAR SISTEMA
# ==========================================

if __name__ == "__main__":

    app.run(debug=True)