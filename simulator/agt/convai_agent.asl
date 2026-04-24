/* ==========================================================
    CoNVaI Agent (Jason BDI)

    Agent states: neutral | infected | vaccinated

    Requires beliefs:
        pinf(pinf)
        pmd(pmd)
        pad(pad)
        popi(popi)
        prd(prd)
        state(initial_state)
    Computes textual parameters:
        pnov
        prpl
        pnw
    Params in Public Profiles:
        pusr
   ========================================================== */

read_history([]).

!start.

+!start: true <-
    updateFeed(true).

+feed_order(Ids): true <-
    -+messages_read(0);
    !process_messages(Ids);
    !act;
    !start.

+!process_messages([]): true <- true.

+!process_messages([Id|Rest]): 
    messages_read(MR) & prd(Prd)
<-
    MR1 = MR + 1;
    -+messages_read(MR1);
    Pread = Prd / MR1;
    ia.U(U1);
    if (U1 <= Pread) {
        !process_single_message(Id)
    };
    !process_messages(Rest).

+!process_single_message(Id): read_history(PastMessages) <-
    .wait(message(Id, Author, Content, Original, Timestamp));
    .wait(message_var(Id, "conversation_id", CId));
    ia.interpretContent(content(Content, PastMessages), Interpretation);
    .if_then_else(in_conversation(CId),
        {
            !read_ms(Id, Author, Content, CId, Interpretation)
        },
        {
            !read_sc(Id, Author, Content, CId, Interpretation)
        }
    );
    -read_history(PastMessages);
    +read_history([Content | PastMessages]).

/* Algorithm 3 */
+!read_sc(Id, Author, Content, CId, [pnov(Pnov), prpl(Prpl), pnw(Pnw)]): 
    pinf(Pinf) & pmd(Pmd)
<-
    -+state(neutral);
    Max1 = 1 - Pnov;
    ia.U(Max1, U1);
    .if_then_else(U1 <= Prpl,
        {
            -+replying(CId, Id);
            readPublicProfile(Author);
            .wait(public_profile(Author, "pusr", Pusr));
            Max2 = 1 - Pusr - Pnw;
            ia.U(Max2, U2);
            ia.U(Max2, U3);
            .if_then_else(U2 <= Pinf,
                { -+state(infected) },
                { .if_then_else(U3 <= Pmd,
                    { -+state(vaccinated) },
                    { .skip }
                )}
            )
        },
        { .skip }
    ).

/* Algorithm 4 */
+!read_ms(Id, Author, Content, CId, [pnov(Pnov), prpl(Prpl), pnw(Pnw)]): 
    state(State) & popi(Popi) & pad(Pad)
<-
    readPublicProfile(Author);
    .wait(public_profile(Author, "pusr", Pusr));
    Max1 = 1 - Pnov - Pusr;
    ia.U(Max1, U1);
    .if_then_else(U1 <= Prpl,
        {
            ia.U(Max2, U2);
            ia.U(Max3, U3);
            ia.U(Max4, U4);
            .wait(message_var(Id, "state", Sk));
            .if_then_else((State == Sk) & (U2 <= Popi),
                {
                    -+replying(CId, Id)
                },
                {
                    .if_then_else(State \== Sk,
                        {
                            .if_then_else(U3 <= Pad,
                                { 
                                    -+replying(CId, Id);
                                    -+state(Sk) 
                                },
                                {
                                    .if_then_else(U4 <= Popi,
                                        { 
                                            -+replying(CId, Id);
                                            -+state(State)
                                        },
                                        { .skip }
                                    )
                                }
                            )
                        },
                        { .skip }
                    )
                }
            )
        },
        { .skip }
    ).

/* f(state) */
/* a_reply(c) */
+!act: state(State) & state(State) \== neutral & replying(CId, Id) & message(Id, _, Content, _, _) <-
    Topics = [];
    PromptParams = [content(Content), state(State)];
    Variables = [public(state(State), conversation_id(CId))];
    ia.createContent(Topics, PromptParams, GeneratedContent);
    comment(Id, Topics, Variables, GeneratedContent).

/* a_new condition is never true with current g */

/* a_skip */
+!act: true <- true.
