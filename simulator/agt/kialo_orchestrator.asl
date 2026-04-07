//debate(id, author, text, parent_id, votes, relation, relation_abs).

/* ===== Initial goal ===== */
!start_debate.

+!start_debate <-
    !next_turn(1).

+!next_turn(ID) : debate(ID, Agent, Text, ParentID, Votes, Relation, RelationAbs) <-
    .print("TURN ", ID, " -> sending to ", Agent);
    .send(Agent, tell, your_turn(ID, Text, ParentID, Votes, Relation, RelationAbs)).

+!next_turn(ID) : not debate(ID, _author, _text, _parent_id, _votes, _relation, _relation_abs) <-
    .print("Debate finished at turn ", ID).

+next(ID) <-
    NewID = ID + 1;
    !next_turn(NewID).