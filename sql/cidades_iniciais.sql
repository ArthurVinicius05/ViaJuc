-- Cidades iniciais para testar os seletores do ViaJuc.
-- O script não cria rotas nem horários fictícios.
-- Pode ser executado mais de uma vez sem duplicar estas cidades.

INSERT INTO cidade (nome, uf)
SELECT dados.nome, dados.uf
FROM (VALUES
    ('Jucurutu', 'RN'),
    ('Caicó', 'RN'),
    ('Natal', 'RN')
) AS dados(nome, uf)
WHERE NOT EXISTS (
    SELECT 1
    FROM cidade existente
    WHERE LOWER(existente.nome) = LOWER(dados.nome)
      AND UPPER(existente.uf) = UPPER(dados.uf)
);
