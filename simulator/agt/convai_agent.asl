/* ==========================================================
    CoNVaI Agent (Jason BDI)

    Agent states: neutral | infected | vaccinated

    Input parameters:
        Pusr
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
    ia.U(U);
    if (U < Pread) {
        !process_single_message(Id)
    };
    !process_messages(Rest).

+!process_single_message(Id): read_history(PastMessages) <-
    .wait(message(Id, Author, Content, Original, Timestamp));
    .wait(message_var(Id, "conversation_id", CId));
    ia.interpretContent(content(Content, PastMessages), Interpretation);
    if_then_else(in_conversation(CId),
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
+!read_sc(Id, Author, Content, CId, [pnov(Pnov), prpl(Prpl), pnw(Pnw)]): true <-
    -+state(neutral);
    Max = 1 - Pnov;
    ia.U(U, Max);
    if_then_else(U < Prpl,
        {
            ?
        },
        {
            nothing
        }
    ).

