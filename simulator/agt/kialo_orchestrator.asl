//debate(id, author, text, parent_id, votes, relation).

/* ===== Initial goal ===== */
!start_debate.

+!start_debate <-
    !next_turn(1).

+!next_turn(ID) : debate(ID, Agent, Text, ParentID, Votes, Relation) <-
    .print("TURN ", ID, " -> sending to ", Agent);
    .send(Agent, tell, your_turn(ID, Text, ParentID, Votes, Relation)).

+!next_turn(ID) : not debate(ID, _, _, _, _, _) <-
    .print("Debate finished at turn ", ID).

+next(ID) <-
    NewID = ID + 1;
    !next_turn(NewID).