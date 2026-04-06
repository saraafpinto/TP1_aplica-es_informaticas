#importa o modulo socket, que permite comunicação em rede (TCP/IP)
import socket

#importa o módulo threading para executar tarefas em paralelo (multithreading)
import threading

#importa o módulo time para controlo de pausas/temporização
import time

#Importa datetime para obter data e hora atuais
from datetime import datetime
import random
import json

#===============================
# CONFIGURAÇÃO DE LIGAÇÃO AO MIRTH
#===============================

#endereço IP do servidor Mirth 
MIRTH_HOST = "127.0.0.1"
MIRTH_PORTA_PEDIDO=5100

#===============================
#CONFIGURAÇÃO DO SEERVIDOR LOCAL
#===============================

#Endereço IP local onde este programa irá receber p relatório
HOST_LOCAL= "127.0.0.1"
#Porta onde o programa ficará à escuta para receber o relatório final 
PORTA_RELATORIO=6001

#===============================
#CONSTANTES MLLP (protocolo HL7)
#===============================

# Byte de início da mensagem HL7 (MLLP Start Block)
MLLP_START = b"\x0b"

# Bytes de fim de mensagem HL7 (MLLP End Block)
MLLP_END = b"\x1c\x0d"

#==============================================
# BASE DE DADOS DO AIDA (Para guardar os pedidos feitos)
#==============================================

import json
import os

FICHEIRO_PEDIDOS = "pedidos.json"

def carregar_pedidos():
    if not os.path.exists(FICHEIRO_PEDIDOS):
        return {}
    try:
        with open(FICHEIRO_PEDIDOS, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def guardar_pedidos_aida(pedidos):
    with open(FICHEIRO_PEDIDOS, "w", encoding="utf-8") as f:
        json.dump(pedidos, f, indent=4)

#==============================================
# FUNCAO PARA CRIAR UMA MENSAGEM HL7 DE PEDIDO
#==============================================

def input_nao_vazio(mensagem):
    while True:
        valor = input(mensagem).strip()
        if valor:
            return valor
        print("Campo obrigatório!")

def validar_data(data):
    if len(data) != 8 or not data.isdigit():
        return False
    try:
        datetime.strptime(data, "%Y%m%d")
        return True
    except ValueError:
        return False

def input_data(mensagem):
    while True:
        data = input(mensagem).strip()
        if validar_data(data):
            return data
        print("Data inválida! Use AAAAMMDD.")

def input_sexo():
    while True:
        sexo = input("Sexo (M/F): ").upper().strip()
        if sexo in ["M", "F"]:
            return sexo
        print("Valor inválido! Use M ou F.")

def input_nif():
    while True:
        nif = input("NIF: ").strip()
        if nif.isdigit() and len(nif) == 9:
            return nif
        print("NIF inválido! Deve ter 9 dígitos.")

def input_opcao(mensagem, opcoes_validas):
    while True:
        valor = input(mensagem).upper().strip()
        if valor in opcoes_validas:
            return valor
        print(f"Opção inválida! Escolha: {', '.join(opcoes_validas)}")


def pedir_dados_admissao():
    print("\n" + "-"*30)
    print(" DADOS PARA ADMISSÃO DO PACIENTE")
    print("-"*30)

    catalogo = {
        "1": {"nome": "Criar Novo Paciente", "evento": "A01"}, # A01 ou A08
        "2": {"nome": "Atualizar Paciente", "evento": "A08"},
        "3": {"nome": "Fundir Pacientes", "evento": "A40"}
    }

    tipo_adm = {
        "1": {"nome": "Urgente", "evento": "URG"}, # A01 ou A08
        "2": {"nome": "Internamento", "evento": "INT"},
        "3": {"nome": "Externo", "evento": "EXT"}
    }

    print("\n--- OPERAÇÕES DISPONÍVEIS ---")
    for chave, info in catalogo.items():
        print(f"{chave}. {info['nome']}")

    while True:
        escolha = input("\nEscolha a operação: ").strip()
        if escolha in catalogo:
            operacao = catalogo[escolha]
            break
        print("Escolha inválida!")

    dados = {}

    dados['tipo'] = operacao['evento']

    if escolha == "3":
        print("\n[MODO FUSÃO] Introduza apenas os identificadores:")
        dados['id_principal'] = input_nao_vazio("ID Destino (O que FICA): ")
        dados['id_antigo'] = input_nao_vazio("ID Antigo (O que vai ser ELIMINADO/FUNDIDO): ")
        
        # Preenchemos o resto com "N/A" ou vazio para não dar erro no template
        dados.update({
            'nome': "FUSAO DE REGISTO", 'nasc': "", 'sexo': "", 
            'nif': "", 'morada': "", 'tipo_adm': "EXT"
        })
        return dados

    # ==========================================================
    # CASO A01 / A08: PRECISA DOS DADOS COMPLETOS
    # ==========================================================
    if escolha == "1":
        print("ID: Será gerado automaticamente.")
        dados['id_principal'] = ""
    else:
        dados['id_principal'] = input_nao_vazio("ID do Paciente: ")

    dados['id_antigo'] = ""
    # Dentro da função pedir_dados_admissao
    apelidos = input_nao_vazio("Apelidos: ").upper()
    nomes_proprios = input_nao_vazio("Nomes Próprios: ").upper()
    # Juntamos no formato HL7: APELIDO^NOME^^
    dados['nome'] = f"{apelidos}^{nomes_proprios}^^"
    dados['nasc'] = input_data("Data Nascimento (AAAAMMDD): ")
    dados['sexo'] = input_sexo()
    dados['nif'] = input_nif()
    dados['morada'] = input_nao_vazio("Morada: ").upper()
    for chave, info in tipo_adm.items():
        print(f"{chave}. {info['nome']}")

    while True:
        escolha_tipo = input("Escolha o tipo de admissão: ").strip()
        if escolha_tipo in tipo_adm:
            dados['tipo_adm'] = tipo_adm[escolha_tipo]['evento']
            break
        print("Escolha inválida!")

    return dados

def registar_paciente_json(dados_adm):
    caminho_arquivo = 'pacientes.json'
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            base_pacientes = json.load(f)
    except:
        base_pacientes = {}

    id_evento = dados_adm.get('tipo')

    # --- CASO A40: APAGAR O ANTIGO ---
    if id_evento == "A40":
        id_old = str(dados_adm.get('id_antigo'))
        if id_old in base_pacientes:
            del base_pacientes[id_old]
        
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            json.dump(base_pacientes, f, indent=4)
        return dados_adm.get('id_principal')

    # --- CASO A01/A08: CRIAR OU ATUALIZAR ---
    id_atual = str(dados_adm.get('id_principal', "")).strip()
    
    if id_atual == "" or id_atual == "0":
        if base_pacientes:
            novo_id = str(max(int(k) for k in base_pacientes.keys()) + 1)
        else:
            novo_id = "1"
    else:
        novo_id = id_atual

    # VERIFICAÇÃO DE SEGURANÇA: Só grava se os dados não forem os "vazios" da fusão
    if dados_adm['nome'] != "FUSAO DE REGISTO":
        base_pacientes[novo_id] = {
            "nome": dados_adm['nome'],
            "nasc": dados_adm['nasc'],
            "sexo": dados_adm['sexo'],
            "nif": dados_adm.get('nif', ""),      # Garante que lê a chave 'nif'
            "morada": dados_adm.get('morada', "") # Garante que lê a chave 'morada'
        }

    with open(caminho_arquivo, 'w', encoding='utf-8') as f:
        json.dump(base_pacientes, f, indent=4, ensure_ascii=False)
    
    # Atualiza o dicionário original para o HL7 levar o ID certo
    dados_adm['id_principal'] = novo_id
    return novo_id
    
def criar_admissao_hl7(dados_manuais):
    novo_id = registar_paciente_json(dados_manuais)
    if not novo_id:
        return "Erro: Não foi possível registar o paciente no JSON."

    # Lógica para o segmento MRG (exclusivo de admissões A40)
    if dados_manuais['tipo'] == "A40":
        conteudo_mrg = f"MRG|{dados_manuais['id_antigo']}|\n" 
    else:
        conteudo_mrg = ""

    # Ler o template de Admissão
    with open('mensagens/Admissão.txt', 'r') as f:
        template = f.read()

    # Preencher com os dados dinâmicos
    mensagem_final = template.format(
        tipo_evento=dados_manuais['tipo'],
        data_hoje=datetime.now().strftime("%Y%m%d%H%M"),
        msg_id=f"ADM{random.randint(1000,9999)}",
        id_principal=novo_id,
        nome=dados_manuais['nome'],
        nasc=dados_manuais['nasc'],
        sexo=dados_manuais['sexo'],
        morada=dados_manuais['morada'],
        nif=dados_manuais['nif'],
        segmento_mrg=conteudo_mrg, 
        tipo_adm=dados_manuais['tipo_adm'],
        id_episodio=f"EP{random.randint(10000,99999)}"
    )

    return mensagem_final

def pedir_dados_pedido():
    print("\n" + "-"*30)
    print(" DADOS DO PEDIDO DE EXAME")
    print("-"*30)

    catalogo = {
        "1": {"nome": "RAIO-X TORAX", "codigo": "M10405"},
        "2": {"nome": "TAC ABDOMINAL", "codigo": "TAC01"},
        "3": {"nome": "HEMOGRAMA", "codigo": "ANAL01"},
        "4": {"nome": "URINA", "codigo": "ANAL02"}
    }

    dados = {}

    dados['id_pac'] = input_nao_vazio("ID do Paciente: ")

    print("\n--- EXAMES DISPONÍVEIS ---")
    for chave, info in catalogo.items():
        print(f"{chave}. {info['nome']}")

    while True:
        escolha = input("Escolha o número do exame: ").strip()
        if escolha in catalogo:
            exame = catalogo[escolha]
            dados['cod_exame'] = exame['codigo']
            dados['exame'] = exame['nome']
            break
        print("Escolha inválida!")

    return dados

def criar_pedido_hl7(fluxo, dados_manuais):
    """
    fluxo: 'requisicao' ou 'cancelar'
    dados_manuais: Dicionário com nome, id, nasc, sexo, etc., vindos do input()
    """

    id_alvo = str(dados_manuais['id_pac'])
    
    # --- PASSO 1: Procurar info extra do paciente no JSON ---
    try:
        with open('pacientes.json', 'r', encoding='utf-8') as f:
            base_pacientes = json.load(f)
        
        # Procura o paciente pelo ID
        paciente = base_pacientes.get(id_alvo)
        
        if not paciente:
            return f"Erro: Paciente com ID {id_alvo} não encontrado no sistema (JSON)."
            
    except FileNotFoundError:
        return "Erro: Ficheiro pacientes.json não encontrado."
    
    emissor, recetor = "AIDA", "PACS"
    
    if dados_manuais['cod_exame'].startswith("ANAL"):
        tipo_msg = "OML^O21"
    else:
        tipo_msg = "ORM^O01"

    if fluxo == 'requisicao':
        acao = "NW"
        extra_obr = "30|" 
    else:
        acao = "CA"
        extra_obr = "|"

    data_atual = datetime.now().strftime("%Y%m%d%H%M%S")
    msg_id = f"A_{data_atual}{random.randint(10, 99)}"

    # 3. Ler o ficheiro de template
    try:
        with open('mensagens/Pedido.txt', 'r', encoding='utf-8') as f:
            template = f.read()

        mensagem_final = template.format(
            emissor=emissor,
            recetor=recetor,
            data_hoje=data_atual,
            tipo=tipo_msg,
            msg_id=msg_id,
            id_paciente=id_alvo,       # Do JSON
            nome_paciente=paciente['nome'],   # Do JSON
            data_nasc=paciente['nasc'],       # Do JSON
            sexo=paciente['sexo'],           # Do JSON
            nif=paciente['nif'],             # Do JSON
            tipo_paciente="I",      
            setor="INT",            
            id_episodio=f"EP{random.randint(100,999)}",
            acao=acao,
            estado="",              
            id_pedido=f"REQ{random.randint(1000,9999)}",
            data_pedido=data_atual,
            cod_exame=dados_manuais['cod_exame'], # Do MENU
            desc_exame=dados_manuais['exame'],     # Do MENU
            extra_obr=extra_obr
        )
        return mensagem_final

    except Exception as e:
        return f"Erro ao gerar HL7: {e}"

#==============================================
# FUNCAO PARA ENVOLVER A MENSAGEM COM MLLP
#==============================================

def envolver_mllp(mensagem):
    # Converte a mensagem para bytes (UTF-8) e adiciona delimitadores MLLP
    return MLLP_START + mensagem.encode("utf-8") + MLLP_END

#==============================================
# FUNCAO PARA REMOVER MLLP DE UMA MENSAGEM
#==============================================

def remover_mllp(dados):
    # Se começar com byte de início, remove-o
    if dados.startswith(MLLP_START):
        dados = dados[1:]

    # Se terminar com bytes de fim, remove-os
    if dados.endswith(MLLP_END):
        dados = dados[:-2]

    #Converte bytes para string (UTF-8), substituindo erros
    return dados.decode("utf-8", errors="replace")

#==============================================
# FUNCAO PARA ESCUTAR RELATÓRIO (SERVIDOR TCP)
#==============================================

def escutar_relatorio():
    # Cria um socket TCP (IPv4)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:

        # Permite reutilizar a porta imediatamente após o programa terminar
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Associa o socket ao endereço e porta definidos
        servidor.bind((HOST_LOCAL, PORTA_RELATORIO))

        # Coloca o servidor à escuta (max. 1 ligação em espera)
        servidor.listen(1)

        #Mensagem informativa
        print(f"Programa A à espera do relatório na porta {PORTA_RELATORIO}...")

        # CICLO WHILE TRUE PARA FICAR SEMPRE À ESCUTA
        while True:
            #Aceita uma ligacao de um cliente (bloqueante)
            conn, addr = servidor.accept()

            # usa o socket da ligacao estabelecida
            with conn:
                print(f"\nLigação recebida de {addr}")
                
                # buffer para acumular dados recebidos
                buffer = b""
                
                # ciclo para recebr dados em blocos
                while True:
                    chunk = conn.recv(4096)

                    if not chunk:
                        break

                    buffer += chunk
                    
                    # se ja recebeu o terminador MLLP, pode parar
                    if MLLP_END in buffer:
                        break

            # mostra
            print("\n======== Relatorio final recebido =======")
            print(remover_mllp(buffer))
            print("===========================================")

#==============================================
# FUNCAO PARA enviar pedido ao mirth (cliente)
#==============================================
            
def enviar_pedido(mensagem):
    # cria a mensagem HL7
    #mensagem = criar_admissao_hl7()
    #mensagem = criar_pedido_hl7()

    # envolve a mensagem com MLLP
    pacote = envolver_mllp(mensagem)

    #cria socket TCP cliente
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as cliente:

        #liga ao servidor Mirth
        cliente.connect((MIRTH_HOST, MIRTH_PORTA_PEDIDO))

        # envia todos os bytes do pacote
        cliente.sendall(pacote)

    #mensagens informativas
    print("\nPedido enviado para o Mirth com sucesso.")
    print("\n === Pedido HL7 ENVIADO ======")
    print(mensagem)
    print("===========================================")

#==============================================
# Ponto de entrada do programa
#==============================================
    
if __name__ == "__main__":
    #mensagem inicial
    print("A iniciar o Programa A...\n")
    
    # cria uma thread para escutar o relatorio em paralelo
    thread_relatorio = threading.Thread(
        target=escutar_relatorio, #funcao a executar
        daemon = True # termina automaticamente com o programa
    )

    #Inicia a thread
    thread_relatorio.start()

    #pequena pausa para garantir que o servidr ja esta pronto
    time.sleep(1)

    # O NOSSO MENU INTERATIVO
    while True:
        print("\n" + "="*45)
        print(" MENU PRINCIPAL - SISTEMA DE PEDIDOS (AIDA)")
        print("="*45)
        print("1. Enviar Novo Pedido de Exame")
        print("2. Cancelar Pedido de Exame")
        print("3. Enviar Admissão de Paciente")
        print("0. Sair do Programa")
        print("="*45)
        
        opcao = input("Escolhe uma opção: ")

        if opcao == "1":
            meus_dados = pedir_dados_pedido()
            
            # Gerar IDs únicos AGORA e guardar no dicionário
            meus_dados['id_pedido'] = f"REQ{random.randint(1000,9999)}"
            meus_dados['id_episodio'] = f"EP{random.randint(100,999)}"
            meus_dados['estado'] = "Ativo"
            meus_dados['data_criacao'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Guardar o pedido no JSON local do Programa A
            pedidos_sistema = carregar_pedidos()
            pedidos_sistema[meus_dados['id_pedido']] = meus_dados
            guardar_pedidos_aida(pedidos_sistema)

            # Criar e enviar a mensagem
            msg = criar_pedido_hl7("requisicao", meus_dados)
            enviar_pedido(msg)
            
        elif opcao == "2":
            id_pac = input_nao_vazio("\nInsira o ID do Paciente para procurar exames: ")
            pedidos_sistema = carregar_pedidos()

            # Filtrar apenas os pedidos "Ativos" deste paciente
            pedidos_ativos = {k: v for k, v in pedidos_sistema.items() if v.get('id_pac') == id_pac and v.get('estado') == "Ativo"}

            if not pedidos_ativos:
                print(f"\n Não foram encontrados exames ativos para o paciente com ID '{id_pac}'.")
            else:
                print(f"\n--- EXAMES ATIVOS PARA O PACIENTE {id_pac} ---")
                lista_ids = list(pedidos_ativos.keys())
                
                # Listar os exames encontrados
                for i, p_id in enumerate(lista_ids, 1):
                    p_info = pedidos_ativos[p_id]
                    print(f"{i}. [{p_id}] {p_info['exame']} (Pedido em: {p_info['data_criacao']})")

                escolha = input("\nEscolha o número do exame a cancelar (ou 0 para voltar): ").strip()

                if escolha.isdigit() and 1 <= int(escolha) <= len(lista_ids):
                    id_escolhido = lista_ids[int(escolha)-1]
                    pedido_a_cancelar = pedidos_ativos[id_escolhido]

                    # Envia a mensagem de cancelamento com os dados originais exatos
                    msg = criar_pedido_hl7("cancelar", pedido_a_cancelar)
                    enviar_pedido(msg)

                    # Atualiza o estado no JSON do AIDA para não voltar a aparecer na lista
                    pedidos_sistema[id_escolhido]['estado'] = "Cancelado"
                    guardar_pedidos_aida(pedidos_sistema)
                    
                    print(f"\n Exame {id_escolhido} cancelado com sucesso no sistema.")
                elif escolha == "0":
                    print("Cancelamento abortado.")
                else:
                    print(" Opção inválida!")
        elif opcao == "3":
            # 1. Pedir dados específicos de admissão
            dados_adm = pedir_dados_admissao()
            # 2. Gerar a mensagem com esses dados
            msg = criar_admissao_hl7(dados_adm)
            # 3. Enviar para o Mirth
            enviar_pedido(msg)
        elif opcao == "0":
            print("A encerrar o Programa A...")
            break
        else:
            print("Opção inválida! Tenta novamente.")