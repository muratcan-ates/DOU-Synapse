
    WITH nearest AS (
        SELECT c.id,
               c.document_id,
               c.chunk_index,
               c.page_number,
               c.slide_number,
               c.section_title,
               c.text,
               c.embedding_space,
               c.embedding <=> CAST(%(query_vector)s AS vector) AS distance
        FROM chunks c
        WHERE c.course_id = %(course_id)s
          AND (
              NOT CAST(%(filter_documents)s AS boolean)
              OR c.document_id = ANY(CAST(%(document_ids)s AS uuid[]))
          )
          AND c.embedding IS NOT NULL
        -- Eşitlik bozma `c.id` DEĞİL: birincil anahtar `gen_random_uuid()` ile
        -- üretiliyor, aynı korpus yeniden ingest edildiğinde eşit mesafeli
        -- satırların sırası değişir (fts.py'de ölçülüp docs/test-report.md
        -- §6.4'te belgelenen kusurla aynı sınıftan — T303). `(document_id,
        -- chunk_index)` belgenin içeriğinden türüyor: aynı materyal yeniden
        -- işlendiğinde aynı sırayı verir.
        ORDER BY distance, c.document_id, c.chunk_index
        LIMIT %(limit)s
    )
    SELECT n.id,
           n.document_id,
           d.file_name,
           n.page_number,
           n.slide_number,
           n.section_title,
           n.text,
           n.embedding_space,
           1 - n.distance AS similarity
    FROM nearest n
    JOIN documents d ON d.id = n.document_id
    ORDER BY n.distance, n.document_id, n.chunk_index
    