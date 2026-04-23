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
    .random(U);
    if (U < Pread) {
        !process_single_message(Id)
    };
    !process_messages(Rest).

+!process_single_message(Id): true <-
    .wait(message(Id, Author, Content, Original, Timestamp));
    .wait(message_var(Id, "conversation_id", CId));
    if_then_else(in_conversation(CId),
        {
            ia.interpretContent(Content, Interpretation);
            !read_ms(Id, Author, Content, CId, Interpretation)
        },
        {
            ia.interpretContent(Content, Interpretation);
            !read_sc(Id, Author, Content, CId, Interpretation)
        }
    ).