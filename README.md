# YouTube do Andrew

**YouTube do Andrew** é um projeto de código aberto para desenvolver uma **skill de pesquisa de vídeos e recuperação de transcrições**, utilizável por diferentes agentes de inteligência artificial.

A proposta é facilitar o acesso ao conteúdo falado de vídeos públicos do YouTube para estudo, pesquisa e análise. Cada agente poderá pesquisar assuntos de seu próprio interesse, localizar vídeos relevantes e trabalhar com informações verificáveis sobre suas fontes.

**O projeto está em fase de pesquisa e desenvolvimento. Ainda não oferece uma skill funcional ou um mecanismo de transcrição validado.**

## O que pretendemos construir

Uma ferramenta que permita a um agente, sem depender de interface gráfica:

- **Pesquisar vídeos públicos** por assuntos, termos ou perguntas.
- **Identificar fontes** por título, canal, endereço e outros metadados disponíveis.
- **Recuperar legendas e transcrições** quando tecnicamente acessíveis, incluindo legendas automáticas.
- **Fornecer texto estruturado** para consulta, resumo, comparação de argumentos e pesquisa, com referência ao vídeo de origem.
- **Oferecer marcações temporais**, quando disponíveis, para localizar trechos no vídeo.
- **Informar claramente os limites**: ausência de legendas, transcrição não recuperável, falhas de rede ou restrições de acesso não serão apresentadas como sucesso.

A ideia não é reproduzir ou baixar vídeos em massa, operar um canal, aumentar visualizações ou simular espectadores. O foco é **pesquisa sobre o conteúdo publicado**.

## Diretrizes de arquitetura

Estamos investigando uma implementação **local-first**, aberta, auditável e interoperável, com os seguintes objetivos:

- **Skill reutilizável:** a ferramenta não será exclusiva de um agente, modelo ou plataforma.
- **Sem navegador gráfico obrigatório:** o fluxo essencial não deve exigir mouse, cliques ou interação humana para cada consulta.
- **Sem chave de API como requisito fundamental:** pretendemos desenvolver e compreender o mecanismo principal, sem tornar a YouTube Data API, serviços pagos ou servidores MCP dependências estruturais.
- **Operação sob demanda:** não é necessário criar uma cópia permanente do catálogo do YouTube nem manter um banco central de vídeos ou transcrições.
- **Fontes identificáveis:** resultados devem preservar endereço, identificação do vídeo e, quando disponíveis, idioma e tempo dos trechos.
- **Falhas transparentes:** caso uma etapa não funcione, a skill deverá relatar a limitação em vez de inventar informações.

A conexão de rede continuará sendo necessária para consultar conteúdo hospedado no YouTube. A proposta de independência diz respeito ao **motor da skill e à ausência de serviços intermediários obrigatórios**, não à eliminação da própria fonte consultada.

## Principal desafio técnico

Localizar um vídeo público e obter sua transcrição são problemas diferentes.

O YouTube pode disponibilizar legendas na interface para visitantes sem login, mas isso **não garante que uma ferramenta automatizada consiga recuperar o texto**. Restrições contra acesso automatizado, mudanças na página e diferenças entre formatos de legendas são obstáculos reais.

Nossa primeira meta experimental é verificar, com código próprio, se é possível:

1. Consultar a página de um vídeo público sem navegador gráfico ou autenticação.
2. Identificar as faixas de legendas disponíveis.
3. **Recuperar o conteúdo textual real** de uma faixa e, quando possível, seus tempos.

Identificar apenas a existência de uma faixa **não equivale** a obter sua transcrição. A viabilidade e a cobertura ainda precisam ser comprovadas em testes reais. Para vídeos sem legendas recuperáveis, transcrição de áudio local poderá ser estudada como alternativa futura, sem presumir acesso garantido ao áudio.

## Estado do projeto

**Planejamento e investigação técnica.** O repositório apresenta, por enquanto, a proposta do produto. **Não há instalação, release funcional, suporte a vídeos específicos ou compatibilidade comprovada para anunciar.**

A publicação de código ocorrerá conforme as funcionalidades forem implementadas e testadas. O README será atualizado para distinguir recursos disponíveis de funcionalidades planejadas.

## Licença e colaboração

O arquivo [LICENSE](LICENSE) existente neste repositório contém a dedicação **CC0 1.0 Universal**. As condições aplicáveis a futuros componentes e dependências serão documentadas junto com sua publicação.

Projeto de **Bobby Dias e Andrew Vox**, no âmbito da **Enterprise**. O objetivo é colaborar no desenvolvimento de ferramentas abertas que permitam aos agentes pesquisar informações com mais autonomia.
