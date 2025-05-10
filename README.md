# Coletor de Dados Supreme Posta

Automatização de coleta de dados da plataforma Suprema Posta com envio automático para o Google BigQuery.

## 📋 Visão Geral

Este projeto foi desenvolvido para automatizar a coleta diária de relatórios da plataforma Suprema Posta. 
O sistema realiza login automático, baixa os relatórios disponíveis e os envia para tabelas estruturadas no Google BigQuery.

### Agendamento Automático

O sistema está configurado para executar automaticamente todos os dias às 00:15 (horário do servidor), garantindo a coleta dos dados do dia anterior. Este horário foi escolhido para:
- Garantir que todos os dados do dia anterior estejam disponíveis
- Evitar horários de pico da plataforma
- Permitir tempo suficiente para retry em caso de falhas

### Relatórios Coletados

- Relatório de Mídia
- Relatório de Registros
- Relatório de Ganhos
- Relatório de Atividades

## 🛠️ Tecnologias Utilizadas

- Python 3.9
- Selenium (automação web)
- Google BigQuery (armazenamento de dados)
- Docker (containerização)
- Chromium (navegador headless)

## ⚙️ Pré-requisitos

- Docker e Docker Compose
- Conta no Google Cloud Platform com BigQuery ativado
- Credenciais de acesso ao Supreme Posta
- Acesso à internet

## 🚀 Configuração e Instalação

### 1. Preparação do Ambiente Google Cloud

1. Acesse o [Console do Google Cloud](https://console.cloud.google.com/)
2. Crie ou selecione um projeto
3. Ative a API do BigQuery
4. Crie uma conta de serviço:
   - Vá em "IAM e Administração" > "Contas de serviço"
   - Clique em "Criar Conta de Serviço"
   - Nome: `supreme-posta-scraper`
   - Atribua as funções:
     * `BigQuery Data Editor`
     * `BigQuery Job User`
   - Crie uma chave em formato JSON
   - Salve como `gcp-key.json`

### 2. Configuração Local

1. Clone o repositório:
```bash
git clone [URL_DO_REPOSITÓRIO]
cd [NOME_DO_DIRETÓRIO]
```

2. Crie o arquivo `.env`:
```env
# Credenciais Supreme Posta
USERNAME=seu_usuario
PASSWORD=sua_senha

# Configurações Google Cloud
GCP_PROJECT_ID=seu-projeto-gcp
BQ_DATASET_ID=seu-dataset
```

3. Coloque o arquivo `gcp-key.json` na raiz do projeto

### 3. Criação do Dataset

No BigQuery, crie o dataset que receberá os dados:

```sql
CREATE DATASET seu-projeto-gcp.seu-dataset
```

## 📦 Execução

Para iniciar a coleta:

```bash
docker-compose up --build
```

O sistema irá:
1. Realizar login na plataforma
2. Baixar os relatórios do dia anterior
3. Processar os dados
4. Enviar para o BigQuery

## 📊 Estrutura dos Dados

Os dados são organizados nas seguintes tabelas:

| Tabela                 | Descrição                  |
| ---------------------- | -------------------------- |
| `relatorio_midia`      | Dados de mídia e campanhas |
| `relatorio_registros`  | Registros de atividades    |
| `relatorio_ganhos`     | Informações financeiras    |
| `relatorio_atividades` | Atividades gerais          |

## 📝 Logs e Monitoramento

- Localização: diretório `logs/`
- Rotação: diária
- Retenção: 7 dias
- Informações registradas:
  * Status de login
  * Download de relatórios
  * Processamento de dados
  * Envio para BigQuery
  * Erros e exceções

## 🔒 Segurança

### Boas Práticas

1. Nunca compartilhe ou comite:
   - Arquivo `.env`
   - `gcp-key.json`
   - Logs
   - Arquivos temporários

2. O `.gitignore` já está configurado para proteger:
   - Credenciais (*.json)
   - Variáveis de ambiente (.env)
   - Logs e temporários

3. Recomendações:
   - Use gerenciamento de segredos em produção
   - Faça rotação periódica das chaves
   - Mantenha as permissões mínimas necessárias

## 🔍 Solução de Problemas

Se encontrar problemas:

1. Verifique os logs em `logs/`
2. Confirme as credenciais no `.env`
3. Valide as permissões no Google Cloud
4. Verifique a conexão com internet
5. Confirme se o Docker está atualizado

## 🤝 Contribuindo

1. Faça um fork do projeto
2. Crie uma branch para sua feature
   ```bash
   git checkout -b feature/nova-funcionalidade
   ```
3. Commit suas alterações
   ```bash
   git commit -m 'Adiciona nova funcionalidade'
   ```
4. Push para a branch
   ```bash
   git push origin feature/nova-funcionalidade
   ```
5. Abra um Pull Request

## 📫 Suporte

Em caso de dúvidas ou problemas:
- Abra uma issue no repositório
- Consulte a documentação do [Google BigQuery](https://cloud.google.com/bigquery/docs)
- Verifique os logs de execução

## ✨ Agradecimentos

Agradecimento especial ao [JP](https://github.com/JoaoPSilvaDev) pela colaboração e conhecimento compartilhado durante o desenvolvimento deste projeto.

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

# Descrição

Um amigo pediu-me que eu desenvolvesse uma aplicação 
capaz de realiziar WebScrapping em um determinado site,
além de desenvolver uma forma de executá-lo com periodicidade.

Sendo assim, desenvolvi este conjunto de programas que 
alcançam essas necessidades.

## Tecnologias Utilizadas

* PostGreSQL
* Selenium
* Google BigQuery
* Docker
* Python

## Configuração das Credenciais

### 1. Criar uma Conta de Serviço no Google Cloud (Recomendado para Produção)

1. Acesse o [Console do Google Cloud](https://console.cloud.google.com/)
2. Selecione seu projeto
3. Vá para "IAM e Administração" > "Contas de serviço"
4. Clique em "Criar Conta de Serviço"
5. Preencha os detalhes:
   - Nome: `supreme-posta-scraper`
   - Descrição: `Conta de serviço para coleta de dados do Supreme Posta`
6. Conceda estas funções:
   - `BigQuery Data Editor`
   - `BigQuery Job User`
7. Clique em "Criar Chave" (formato JSON)
8. Salve o arquivo JSON como `gcp-key.json` na raiz do projeto

### 2. Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com:

```env
# Credenciais do Supreme Posta
USERNAME=seu_usuario_supreme_posta
PASSWORD=sua_senha_supreme_posta

# Configurações do Google Cloud
GCP_PROJECT_ID=seu-projeto-id
BQ_DATASET_ID=nome-do-seu-dataset
```

### 3. Criar Dataset no BigQuery

1. Acesse o BigQuery no Console do Google Cloud
2. Crie um novo dataset:
   ```sql
   CREATE DATASET seu-projeto-id.nome-do-seu-dataset
   ```

### 4. Executando com Docker

Para executar o projeto:

```bash
# Construir e iniciar os containers
docker-compose up --build
```

### 5. Requisitos do Sistema

* Docker e Docker Compose instalados
* Acesso à internet
* Credenciais do Suprema Posta válidas
* Projeto configurado no Google Cloud com BigQuery habilitado

### Notas de Segurança

1. Nunca comite a chave de conta de serviço no controle de versão
2. O arquivo `.gitignore` já está configurado para ignorar:
   - Arquivos de credenciais (*.json)
   - Variáveis de ambiente (.env)
   - Logs e arquivos temporários
3. Use gerenciamento de segredos em produção
4. Faça rotação periódica das chaves de conta de serviço
5. Siga o princípio do menor privilégio ao atribuir funções

### Estrutura de Dados

Os dados são coletados e enviados para tabelas específicas no BigQuery:

1. `relatorio_midia` - Relatórios de mídia
2. `relatorio_registros` - Relatórios de registros
3. `relatorio_ganhos` - Relatórios de ganhos
4. `relatorio_atividades` - Relatórios de atividades

### Logs e Monitoramento

Os logs são armazenados no diretório `logs/` e incluem:
- Informações de execução
- Erros e exceções
- Status das coletas
- Confirmações de envio para o BigQuery

### Suporte

Em caso de dúvidas ou problemas:
1. Verifique os logs em `logs/`
2. Confirme as credenciais no arquivo `.env`
3. Verifique as permissões da conta de serviço no Google Cloud
4. Certifique-se de que o Docker está atualizado e funcionando corretamente
