-- database: /path/to/database.db
-- Pokretanje transakcije za integritet podataka
BEGIN TRANSACTION;

-- 1. Ažuriranje postojećih lekcija (zamjena WAITING_GENERATION)
UPDATE lessons
SET
  content = '[{"title": "Što je zapravo biologija?", "content": "Zamisli biologiju kao najveći koncert na svijetu. Sve, od bakterije do plavog kita, svira u istom orkestru. Biologija je znanost koja proučava taj život, njegove zakone i kako svi ti instrumenti rade zajedno."}, {"title": "Znanstvena metoda", "content": "Da bismo razumjeli glazbu života, moramo imati metodu: opažanje, postavljanje pitanja, hipoteza i eksperiment. Bez toga, to je samo buka, a ne znanost."}]'
WHERE
  subject = 'Biologija'
  AND topic LIKE '1.%';

UPDATE lessons
SET
  content = '[{"title": "Elementi života", "content": "99% tvog tijela čine samo četiri elementa: C, H, O i N. To su tvoje osnovne žice na gitari. Bez njih nema melodije."}, {"title": "Voda i biopolimeri", "content": "Voda je pozornica na kojoj se sve događa. Ugljikohidrati su brza energija (ritam), lipidi su rezerve, a proteini su tehničari koji popravljaju opremu."}]'
WHERE
  subject = 'Biologija'
  AND topic LIKE '2.%';

UPDATE lessons
SET
  content = '[{"title": "DNA: Glavni bubnjar", "content": "DNA je nacrt za sve. Sastoji se od nukleotida (A, T, C, G). To su note koje određuju hoćeš li biti čovjek ili kaktus."}, {"title": "RNA i sinteza", "content": "RNA je prijenosnik poruke. Ona uzima note od DNA i nosi ih do ribosoma gdje se stvaraju proteini. To je proces od pisanja pjesme do izvedbe."}]'
WHERE
  subject = 'Biologija'
  AND topic LIKE '3.%';

UPDATE lessons
SET
  content = '[{"title": "Citologija - Građa stanice", "content": "Stanica je osnovna jedinica. Jezgra je mozak (dirigent), mitohondriji su elektrana (pojačala), a membrana je osiguranje na ulazu."}, {"title": "Razlike stanica", "content": "Biljne stanice imaju kloroplaste (solarne ploče) i stijenku, dok životinjske imaju centriole. Oboje su vrhunski opremljeni studiji za život."}]'
WHERE
  subject = 'Biologija'
  AND topic LIKE '4.%';

UPDATE lessons
SET
  content = '[{"title": "Mitoza i Mejoza", "content": "Mitoza je kopiranje - jedna stanica postane dvije identične (rast). Mejoza je stvaranje zvijezda - nastaju spolne stanice za novu generaciju."}, {"title": "Kontrola ciklusa", "content": "Kad kontrola zakaže, stanice se dijele bez prestanka. To je rak - koncert koji je izmakao kontroli i uništava pozornicu."}]'
WHERE
  subject = 'Biologija'
  AND topic LIKE '5.%';

-- 2. Ubacivanje novih lekcija (6 i 7) koje su nedostajale
INSERT OR IGNORE INTO
  lessons (subject, topic, content)
VALUES
  (
    'Biologija',
    '6. Razlika životinjskih carstava',
    '[{"title": "Klasifikacija životinja", "content": "Životinje dijelimo prema simetriji i građi. Imaš beskralježnjake (bez kičme) i svitkovce (s kičmom)."}, {"title": "Evolucijski skok", "content": "Od spužvi koje samo sjede i filtriraju vodu, do sisavaca koji imaju najsloženije mozgove. Svako carstvo ima svoju solo dionicu."}]'
  ),
  (
    'Biologija',
    '7. Biosistematika',
    '[{"title": "Red u kaosu", "content": "Sistematika razvrstava bića u grupe (Domena, Carstvo, Koljeno...). To je kao slaganje playliste po žanrovima."}, {"title": "Binarna nomenklatura", "content": "Svako biće ima dva imena (npr. Homo sapiens). Prvo je prezime (rod), drugo je ime (vrsta). Tako se znanstvenici razumiju širom svijeta."}]'
  );

-- 3. Dodavanje pitanja za nove lekcije (auditabilnost i praćenje progresa)
INSERT INTO
  questions (lesson_id, question, answer, options, q_type)
SELECT
  id,
  'Što čini binarnu nomenklaturu?',
  'Ime roda i ime vrste',
  '["Ime roda i porodice", "Ime vrste i carstva", "Ime roda i ime vrste", "Samo latinsko ime"]',
  'text'
FROM
  lessons
WHERE
  topic = '7. Biosistematika';

COMMIT;
