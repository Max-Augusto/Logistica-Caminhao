# Betim Express - Sistema de Gestão de Logística e Assinaturas

O **Betim Express** é uma plataforma robusta de gestão logística desenvolvida para transportadoras e motoristas independentes. O sistema centraliza o controle de fretes, despesas operacionais, abastecimentos e comissões automáticas, oferecendo uma interface intuitiva para motoristas em campo e um painel analítico potente para administradores.

## 🚀 Arquitetura e Tech Stack

O projeto foi construído com foco em escalabilidade, segurança e eficiência de dados:

-   **Backend:** [Django](https://www.djangoproject.com/) (Python) - Framework de alto nível para desenvolvimento rápido e seguro.
-   **Banco de Dados:** [PostgreSQL](https://www.postgresql.org/) - Relacional de alta performance para integridade de dados financeiros.
-   **Infraestrutura:** [Railway](https://railway.app/) - CI/CD integrado para deploy contínuo e monitoramento.
-   **Frontend:** HTML5, CSS3 (Vanilla) e JavaScript para uma experiência fluida e responsiva.

## 🔗 Integrações Chave

### 💳 Checkout Transparente & Webhooks (Mercado Pago)
Integração completa com a API do **Mercado Pago** para gestão de assinaturas recorrentes (SaaS).
-   **Webhooks:** Processamento em tempo real de notificações de pagamento e atualizações de assinatura.
-   **Gestão Dinâmica:** O valor da assinatura é calculado automaticamente com base no tamanho da frota (número de veículos cadastrados).

### 📧 Sistema de E-mails (Resend / Anymail)
Infraestrutura de entrega de e-mails de alta confiabilidade.
-   **Anymail:** Camada de abstração que permite a troca rápida de provedores.
-   **Resend:** Utilizado para envio de e-mails transacionais (confirmação de pagamento, alertas de sistema).
-   **Configuração DNS:** Integrado com suporte a **SPF, DKIM e DMARC** para máxima entregabilidade e prevenção de spam.

## 🛡️ Segurança e Infraestrutura

-   **Gestão de Variáveis:** Configuração segura via arquivos `.env` e variáveis de ambiente no Railway.
-   **Autenticação:** Sistema de login seguro com integração **Google Social Login** via Django AllAuth.
-   **Controle de Acesso:** Decorators customizados para validação de status de assinatura e permissões de nível (Admin vs Motorista).

## ✨ Funcionalidades Principais

-   📊 **Dashboard Analítico:** Visualização de fretes, gastos operacionais, lucro líquido e gráficos de distribuição de despesas.
-   🚛 **Gestão de Frota:** Cadastro e controle de veículos e motoristas vinculados.
-   ⛽ **Média de Consumo:** Cálculo automático de eficiência de combustível baseado em registros de KM.
-   💰 **Comissões Automáticas:** Sincronização em tempo real de comissões de motoristas a cada novo frete registrado.
-   📄 **Relatórios PDF:** Geração de extratos mensais detalhados para motoristas e fechamentos financeiros.
-   🔔 **Notificações Transacionais:** Envio automático de recibos e comunicações via e-mail.

## 🛠️ Instalação Local

1.  Clone o repositório:
    ```bash
    git clone https://github.com/seu-usuario/logistica-caminhao.git
    ```
2.  Crie e ative um ambiente virtual:
    ```bash
    python -m venv venv
    source venv/bin/activate  # ou venv\Scripts\activate no Windows
    ```
3.  Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```
4.  Configure o arquivo `.env` com as chaves do Mercado Pago e Resend.
5.  Rode as migrações e o servidor:
    ```bash
    python manage.py migrate
    python manage.py runserver
    ```

---
Desenvolvido por **Max Augusto** - Focado em entregar soluções reais para problemas reais de logística.
