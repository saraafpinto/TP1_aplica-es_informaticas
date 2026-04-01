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

def criar_admissao_hl7():
    # 1. Dados que viriam do teu formulário/input
    tipo = "A08" # Ou "A08"
    id_principal = "1458085"
    id_antigo = "1587559" # Só importa se for A40

    # 2. Lógica para o segmento MRG 
    if tipo == "A40":
        # Se for fusão, cria a linha do MRG com o ID antigo 
        conteudo_mrg = f"MRG|{id_antigo}|\n" 
    else:
        # Se for atualização, a linha fica vazia
        conteudo_mrg = ""

    # 3. Ler e preencher o TXT
    with open('mensagens/Admissão.txt', 'r') as f:
        template = f.read()

    mensagem_final = template.format(
        tipo_evento=tipo,
        data_hoje=datetime.now().strftime("%Y%m%d%H%M"),
        msg_id="A2015050514",
        id_principal=id_principal,
        nome="CAMPOS^LUIS^CARDOSO^^",
        nasc="19950204",
        sexo="M",
        morada="RUA ESCULTOR BARATA LINDO 3^^PORTO^PORTO^4000",
        nif="0",
        segmento_mrg=conteudo_mrg, # Aqui entra a linha extra ou o vazio
        tipo_adm="URG",
        id_episodio="15050046"
    )

    return mensagem_final

from datetime import datetime
import random

def criar_pedido_hl7():
    """
    fluxo: 'requisicao' ou 'cancelar'
    tipo_pedido: 'ORM^O01' (Radiologia) ou 'OML^O21' (Laboratório)
    """
    emissor, recetor = "AIDA", "PACS"
    fluxo="requisicao"
    
    # 1. Lógica de Fluxo para o Programa A
    if fluxo == 'requisicao':
        acao = "NW" 
        estado = ""      
        extra_obr = "30|" 
    elif fluxo == 'cancelar':
        acao = "CA" 
        estado = ""      
        extra_obr = "|"
    else:
        return "Erro: O Programa A só pode requisitar ou cancelar."

    # 2. Gerar Timestamps e IDs
    data_atual = datetime.now().strftime("%Y%m%d%H%M%S")
    msg_id = f"A_{data_atual}{random.randint(10, 99)}"

    # 3. Ler o ficheiro de template
    try:
        with open('mensagens/Pedido.txt', 'r', encoding='utf-8') as f:
            template = f.read()
    except FileNotFoundError:
        return "Erro: Ficheiro mensagens/Pedido.txt não encontrado."

    # 4. Preencher o template com TODOS os campos dinâmicos
    mensagem_final = template.format(
        emissor=emissor,
        recetor=recetor,
        data_hoje=data_atual,
        tipo="ORM^O01",      # MSH-9 (ORM^O01 ou OML^O21)
        msg_id=msg_id,
        id_paciente="50626",
        nome_paciente="CONCEICAO SERRANO^MARIA",
        data_nasc="19411012",
        sexo="F",
        nif="28006303",
        tipo_paciente="I",      # PV1-2: 'I' (Internamento) ou 'O' (Outpatient/Ambulatório)
        setor="INT",            # PV1-3: Ex: 'INT', 'URG', 'RAD'
        id_episodio="15002727",
        acao=acao,              # ORC-1: 'NW' ou 'CA'
        estado=estado,          # ORC-5: Vazio no A, preenchido pelo B (CM, IP, HC)
        id_pedido="4727374", 
        data_pedido=data_atual,
        cod_exame="M10405",
        desc_exame="TORAX, UMA INCIDENCIA",
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
            
def enviar_pedido():
    # cria a mensagem HL7
    #mensagem = criar_admissao_hl7()
    mensagem = criar_pedido_hl7()

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

    # espera input do utilizador antes de enviar o pedido
    input("Prime Enter para enviar o pedido de exame...")

    # encia o pedido HL7
    enviar_pedido()

    # espera o input antes de terminar o programa
    input("Prime Enter para terminar o programa A..")