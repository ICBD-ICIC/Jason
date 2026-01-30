+your_turn : true <-
    .wait(initiation_done);
    !act;
    .my_name(Name);
    .send(orchestrator, tell, done(Name)).  

+finish : true <-
    !update_affectivity.

+!initiate_affectivity : 
    political_standpoint(PS) &
    demographics(D) &
    persona_description(PD)
<-
    +love(republicans, 10);
    +love(democrats, 10);
    +hate(republicans, 10);
    +hate(democrats, 10);
    +initiation_done;
    .print("LR=", LR, " LD=", LD, " HR=", HR, " HD=", HD).

/* +!initiate_affectivity : 
    political_standpoint(PS) &
    demographics(D) &
    persona_description(PD)
<-
    ia.initiateAffectivity(love, republicans, PS, D, PD, LR);
    ia.initiateAffectivity(love, democrats, PS, D, PD, LD);
    ia.initiateAffectivity(hate, republicans, PS, D, PD, HR);
    ia.initiateAffectivity(hate, democrats, PS, D, PD, HD);
    +love(republicans, LR);
    +love(democrats, LD);
    +hate(republicans, HR);
    +hate(democrats, HD);
    +initiation_done;
    .print("LR=", LR, " LD=", LD, " HR=", HR, " HD=", HD). */

+!update_affectivity :     
    political_standpoint(PS) &
    demographics(D) &
    persona_description(PD) &
    love(republicans, LR) &
    love(democrats, LD) &
    hate(republicans, HR) &
    hate(democrats, HD) 
<-
    ia.updateAffectivity(love, republicans, LR, PS, D, PD, Content, NewLR);
    ia.updateAffectivity(love, democrats, LD, PS, D, PD, Content, NewLD);
    ia.updateAffectivity(hate, republicans, HR, PS, D, PD, Content, NewHR);
    ia.updateAffectivity(hate, democrats, HD, PS, D, PD, Content, NewHD);
    -+love(republicans, NewLR);
    -+love(democrats, NewLD);
    -+hate(republicans, NewHR);
    -+hate(democrats, NewHD);
    .print("LR=", NewLR, " LD=", NewLD, " HR=", NewHR, " HD=", NewHD).

+!act : 
    political_standpoint(PS) &
    demographics(D) &
    persona_description(PD)
<-
    updateFeed;
    .wait(feed_order(FeedList));
    !collect_messages(FeedList, "", ConversationList);
    ia.reply(PS, D, PD, ConversationList, Response);
    FeedList = [Last | _];
    comment(Last, [], [], Response).

+!collect_messages([] , Conversation, Conversation) : true <- true.

+!collect_messages([ID|Tail], Conversation, Result) : true <-
    .wait(message(ID, Author, Content, _, _));
    .concat("@", Author, ": ", Content, Post);
    .concat(Post, Conversation, UpdatedConversation);
    !collect_messages(Tail, UpdatedConversation, Result).