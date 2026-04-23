/* ==========================================================
    CoNVaI Agent (Jason BDI)

    Agent states: neutral | infected | vaccinated

    Input parameters:
        Pinf
        Pmd
        Pad
        Popi
        Prd
        state(Initial_State)
    Computed textual parameters:
        Pnov
        Prpl
        Pnw
    Params in Public Profiles:
        Pusr
   ========================================================== */

conversation_counter(0).
read_history([]).

+!start: true <-
    updateFeed(true).

+feed_order(Ids): true <-
    -+messages_read(0);
    !process_messages(Ids).

+!process_messages([]): true <- true.

+!process_messages([Id|Rest]): true <-
    messages_read(MR);
    MR1 = MR + 1;
    -+messages_read(MR1);
    prd(Prd);
    Pread = Prd / MR1;
    ia.U(U1);
    if (U1 < Pread) {
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
    ia.U(U1, Max1);
    if_then_else(U1 <= Prpl,
        {
            -+replying(CId);
            readPublicProfile(Author);
            .wait(public_profile(Author, "pusr", Pusr));
            Max2 = 1 - Pusr - Pnw;
            ia.U(U2, Max2);
            ia.U(U3, Max2);
            if_then_else(U2 <= Pinf,
                { -+state(infected) },
                { if_then_else(U3 <= Pmd,
                    { -+state(vaccinated) },
                    { true }
                )}
            )
        },
        { true }
    ).

/* Algorithm 4 */
+!read_ms(Id, Author, Content, CId, [pnov(Pnov), prpl(Prpl), pnw(Pnw)]): 
    state(State) & popi(Popi) & pad(Pad)
<-
    readPublicProfile(Author);
    .wait(public_profile(Author, "pusr", Pusr));
    Max1 = 1 - Pnov - Pusr;
    ia.U(U1, Max1);
    if_then_else(U1 <= Prpl,
        {
            ia.U(U2);
            ia.U(U3);
            ia.U(U4);
            .wait(message_var(Id, "state", Sk));
            if_then_else((State == Sk) & (U2 <= Popi),
                {
                    -+replying(CId)
                },
                {
                    if_then_else(State \== Sk,
                        {
                            if_then_else(U3 <= Pad,
                                { 
                                    -+replying(CId);
                                    -+state(Sk) 
                                },
                                {
                                    if_then_else(U4 <= Popi,
                                        { 
                                            -+replying(CId);
                                            -+state(State)
                                        },
                                        { true }
                                    )
                                }
                            )
                        },
                        { true }
                    )
                }
            )
        },
        { true }
    ).
