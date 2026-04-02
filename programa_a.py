#importa o modulo socket, que permite comunicação em rede (TCP/IP)
import socket

#importa o módulo threading para executar tarefas em paralelo (multithreading)
import threading

#importa o módulo time para controlo de pausas/temporização
import time

#Importa datetime para obter data e hora atuais
from datetime import datetime
import random

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

    dados = {}

    dados['tipo'] = input_opcao(
        "Tipo de Evento (A08 / A40): ", ["A08", "A40"]
    )

    dados['id_principal'] = input_nao_vazio("ID/Processo Principal: ")

    dados['id_antigo'] = ""
    if dados['tipo'] == "A40":
        dados['id_antigo'] = input_nao_vazio("ID Antigo para Fusão: ")

    dados['nome'] = input_nao_vazio("Nome Completo: ").upper()
    dados['nasc'] = input_data("Data Nascimento (AAAAMMDD): ")
    dados['sexo'] = input_sexo()
    dados['nif'] = input_nif()
    dados['morada'] = input_nao_vazio("Morada: ").upper()

    dados['tipo_adm'] = input_opcao(
        "Tipo Admissão (URG/INT/EXT): ", ["URG", "INT", "EXT"]
    )

    return dados


def criar_admissao_hl7(dados_manuais):
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
        id_principal=dados_manuais['id_principal'],
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

    dados['nome'] = input_nao_vazio("Nome Completo: ").upper()
    dados['id_pac'] = input_nao_vazio("ID do Paciente: ")
    dados['nif'] = input_nif()
    dados['nasc'] = input_data("Data Nascimento (AAAAMMDD): ")
    dados['sexo'] = input_sexo()

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
    except FileNotFoundError:
        return "Erro: Ficheiro mensagens/Pedido.txt não encontrado."

    # 4. Preencher o template com os DADOS DA DORA + Lógica do Sistema
    mensagem_final = template.format(
        emissor=emissor,
        recetor=recetor,
        data_hoje=data_atual,
        tipo=tipo_msg,          # Mantemos automático conforme o teu pedido
        msg_id=msg_id,
        id_paciente=dados_manuais['id_pac'],    # DINÂMICO
        nome_paciente=dados_manuais['nome'],    # DINÂMICO
        data_nasc=dados_manuais['nasc'],        # DINÂMICO
        sexo=dados_manuais['sexo'],              # DINÂMICO
        nif=dados_manuais['nif'],                # DINÂMICO
        tipo_paciente="I",      
        setor="INT",            
        id_episodio=f"EP{random.randint(100,999)}", # Gerado na hora
        acao=acao,                               # Automático (NW ou CA)
        estado="",              
        id_pedido=f"REQ{random.randint(1000,9999)}", # ID de pedido único
        data_pedido=data_atual,
        cod_exame=dados_manuais['cod_exame'],
        desc_exame=dados_manuais['exame'],      # DINÂMICO
        extra_obr=extra_obr
    )

    return mensagem_final

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

    # debug: mostra primeiros bytes enviados
    print("DEBUG bytes enviados:", pacote[:10])

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
            # 1. Pedir os dados à Dora
            meus_dados = pedir_dados_pedido()
            # 2. Gerar a mensagem passando esses dados
            msg = criar_pedido_hl7("requisicao", meus_dados)
            # 3. Enviar
            enviar_pedido(msg)
            
        elif opcao == "2":
            # 1. Pedir os dados (para saber qual paciente cancelar)
            meus_dados = pedir_dados_pedido()
            # 2. Gerar a mensagem de cancelamento
            msg = criar_pedido_hl7("cancelar", meus_dados)
            # 3. Enviar
            enviar_pedido(msg)
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