/* ==========================================================
    Available Environment Actions

    updateFeed
    updateFeed(+IncludePublicVars)
        IncludePublicVars: boolean (optional, default false)
        Percepts added: message(+Id, +Author, +Content, +Original, +Timestamp)
                        reaction(+Id, +Author, +Reaction)
                        feed_order(+Ids)
                        message_var(+Id, +Key, +Value)  [only if IncludePublicVars = true]

    searchContent(+Topic)
    searchContent(+Topic, +IncludePublicVars)
        Topic: string/atom
        IncludePublicVars: boolean (optional, default false)
        Percepts added: message(+Id, +Author, +Content, +Original, +Timestamp)
                        reaction(+Id, +Author, +Reaction)
                        feed_order(+Ids)
                        message_var(+Id, +Key, +Value)  [only if IncludePublicVars = true]

    searchAuthor(+Author)
    searchAuthor(+Author, +IncludePublicVars)
        Author: string/atom
        IncludePublicVars: boolean (optional, default false)
        Percepts added: message(+Id, +Author, +Content, +Original, +Timestamp)
                        reaction(+Id, +Author, +Reaction)
                        feed_order(+Ids)
                        message_var(+Id, +Key, +Value)  [only if IncludePublicVars = true]

    createPost(+Topics, +Variables, +Content)
        Topics: list of strings/atoms, e.g. [tech, news, "floods"]
        Variables: map of key(value) pairs, e.g. [sentiment(negative), ...]
        Content: string

    repost(+Id)
        Id: number

    comment(+Id, +Topics, +Variables, +Content)
        Id: number
        Topics: list of strings/atoms, e.g. [tech, news, "floods"]
        Variables: map of key(value) pairs, e.g. [sentiment(negative), ...]
        Content: string

    react(+Id, +Reaction)
        Id: number
        Reaction: string/atom, e.g. like or "love"

    ask(+Query)
        Queries the common knowledge base.
        Query: any knowledge literal, e.g. weather(london, W)
        Percepts added: grounded literals matching the query, e.g. weather(london, sunny)

    createLink(+Agent)
        Agent: string/atom
        Percepts added: follows(Agent) for self        
                        followed_by(Self) for target

    removeLink(+Agent)
        Agent: string/atom
        Percepts removed: follows(Agent) for self
                          followed_by(Self) for target

    readPublicProfile(+Agent)
        Agent: string/atom 
        Percepts added: public_profile(Agent, Attribute, Value)
========================================================== */

/* ==========================================================
   Available Internal Actions

    ia.createContent(+Topic, +Variables, -Content)
        Topic: string/atom
        Variables: map of key(value) pairs, e.g. [sentiment(negative), ...]
        Content: string

    ia.interpretContent(+Content, -Interpretation)
        Content: string
        Interpretation: map of key(value) pairs, e.g. [sentiment(negative), ...]
========================================================== */

mem(crearPublicacion([cambio_climatico], [sentimiento(negativo)]), [msg(1)], t1).
mem(buscarContenido("cambio_climatico", true), [msg(1, sentimiento(negativo)), msg(2, sentimiento(negativo))], t2).

!start.

+!start: true <-
    updateFeed(false);
    .wait(feed_order([M2]));
    +mem(actualizarFeed(false), msg(M2), t3);

    searchContent("cambio_climatico", false);
    .wait(feed_order([M2, M1]));
    +mem(buscarContenido("cambio_climatico", false), [msg(M2), msg(M1)], t4);

    searchAuthor(bob, true);
    .wait(feed_order([M2]));
    .wait(message_var(M2, sentimiento, SentimientoM2));
    +mem(buscarAutor(bob, true), [msg(M2, sentimiento(SentimientoM2))], t5);

    TopicsM4 = [inundaciones];
    VarsM4   = [concientizar(true), emocion(preocupacion)];
    ia.createContent(TopicsM4, VarsM4, ContenidoM4);
    createPost(TopicsM4, VarsM4, ContenidoM4);
    +mem(crearPublicacion(TopicsM4, VarsM4), ContenidoM4, t6);

    .wait(10000);
    updateFeed(false);
    .wait(feed_order([M4 | OtherIds]));
    react(M4, me_encanta);
    +mem(reaccionar(M4, me_encanta), msg(M4, reaccion(me_encanta)), t7);

    ask(norma(X));
    !wait_n_normas(3, Normas);
    +mem(consultarNorma(norma(X)), Normas, t8);

    createLink(carol);
    +mem(crearVinculo(carol), none, t9).

+!wait_n_normas(N, Normas): true <-
    .wait(norma(_));
    .findall(Y, norma(Y), L);
    .length(L, Len);
    if (Len >= N) {
        Normas = L;
    } else {
        !wait_n_normas(N, Normas);
    }.

+followed_by(dave): true <-
    readPublicProfile(dave);
    .wait(public_profile(dave, _, _));
    .findall(public_profile(dave, Attr, Val), public_profile(dave, Attr, Val), PerfilDave);
    +mem(leerPerfilPublico(dave), PerfilDave, t10).

/* ==========================================================
   PolÃ­tica de actualizaciÃ³n de memoria (pi)
   Se activa cuando la memoria alcanza 10 registros y retiene
   Ãºnicamente los 5 mÃ¡s recientes.
========================================================== */
+mem(Action, Content, Timestamp)[source(self)]: true <-
    .findall(mem(A, C, T), mem(A, C, T)[source(self)], Records);
    .length(Records, N);
    if (N >= 10) {
        .sort(Records, Sorted);
        .length(Sorted, Total);
        ToDrop = Total - 5;
        for (.range(I, 0, ToDrop - 1)) {
            .nth(I, Sorted, mem(Ai, Ci, Ti));
            -mem(Ai, Ci, Ti)[source(self)];
        }
    }.
