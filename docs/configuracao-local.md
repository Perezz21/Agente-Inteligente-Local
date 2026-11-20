# Configuração local do agente

O código é o mesmo para diferentes computadores. Cada instalação tem seu próprio
Ollama, banco MySQL e arquivo `.env` local.

## Preparação

1. Instale Python, MySQL e Ollama compatíveis com o projeto.
2. Crie o ambiente virtual e instale dependências:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

3. Disponibilize o banco `agente_experimental` na instalação MySQL local.
   A criação e os dados desse banco devem vir do script SQL experimental do projeto;
   este arquivo não substitui o script.
4. No MySQL, crie um usuário **exclusivo** para o agente (execute em uma sessão
   administrativa e escolha uma senha nova localmente):

```sql
CREATE USER 'agente_leitura'@'localhost' IDENTIFIED BY 'SENHA_ESCOLHIDA_LOCALMENTE';
GRANT SELECT ON agente_experimental.* TO 'agente_leitura'@'localhost';
SHOW GRANTS FOR 'agente_leitura'@'localhost';
```

5. Copie `.env.example` para `.env` na raiz e preencha apenas no computador local.
   O `.env` não deve ser enviado ao GitHub.

```powershell
Copy-Item .env.example .env
```

6. Baixe o modelo necessário no Ollama, por exemplo:
   `ollama pull qwen3.5:4b`.

## Execução

```powershell
python -m src.testar_banco
python -m src.main
```

O projeto procura `.env` a partir da raiz do repositório, independentemente
do diretório de execução. Variáveis já definidas no ambiente do processo
**prevalecem** sobre os valores do `.env`.

Em outra máquina, repita a instalação com credenciais próprias. Nunca copie
credenciais nem a conta administrativa entre computadores. Se MySQL estiver
em outro servidor, são necessárias configuração de rede e conexão protegida;
não exponha o servidor MySQL diretamente à internet.

**Segurança:** a conta deve ter somente SELECT. Credenciais previamente
versionadas devem ser trocadas; removê-las do arquivo atual não limpa o histórico.
