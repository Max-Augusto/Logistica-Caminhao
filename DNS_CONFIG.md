# Guia de Configuração DNS: Registro.br + Resend

Para garantir que os e-mails do sistema **Betim Express** cheguem à caixa de entrada (e não no spam), é fundamental configurar os registros SPF e DKIM no seu domínio `betimexpress.com.br` dentro do Registro.br.

## Passo 1: Obter os registros no Resend
1. Acesse o dashboard do [Resend](https://resend.com/domains).
2. Clique no seu domínio (`betimexpress.com.br`).
3. Você verá uma lista de registros DNS (geralmente 2 ou 3 registros do tipo **MX**, **TXT** e **CNAME**).
4. Copie os valores de **Hostname** (ou Name) e **Value** (ou Content).

## Passo 2: Configurar no Registro.br
1. Acesse o site do [Registro.br](https://registro.br/).
2. Faça login e clique no domínio `betimexpress.com.br`.
3. Role até a seção **DNS** e clique em **Editar Zona**.
4. Clique em **Nova Entrada**.

### Adicionando registros DKIM (Geralmente CNAME)
Para cada registro CNAME que o Resend fornecer:
- **Tipo**: Selecione `CNAME`.
- **Nome**: Cole o Hostname fornecido (ex: `resend._domainkey`).
- **Dados**: Cole o Value fornecido.

### Adicionando/Atualizando o SPF (Registro TXT)
O Resend fornecerá um registro do tipo `TXT`.
- **Tipo**: Selecione `TXT`.
- **Nome**: Deixe em branco (ou coloque `@`).
- **Dados**: Cole o Value fornecido (ex: `v=spf1 include:amazonses.com ~all` - *Nota: o Resend usa infraestrutura da AWS*).

> [!IMPORTANT]
> Se você já tiver um registro SPF (começando com `v=spf1`), **NÃO crie um novo**. Em vez disso, Edite o existente e adicione o include do Resend antes do `~all`. Ex: `v=spf1 include:_spf.google.com include:amazonses.com ~all`.

## Passo 3: Verificar no Resend
Após salvar no Registro.br, volte ao painel do Resend e clique em **Verify**.
> [!NOTE]
> Essa propagação pode levar de 5 minutos a 24 horas, mas no Registro.br costuma ser rápido (em torno de 30 minutos).

---
**Dica**: Se os registros aparecerem como "Unverified" por muito tempo, verifique se você não copiou o domínio duas vezes no campo Nome (ex: `resend._domainkey.betimexpress.com.br` em vez de apenas `resend._domainkey`).
