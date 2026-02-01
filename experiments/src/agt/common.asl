+your_turn : true <-
    .wait(initiation_done);
    !act;
    .my_name(Name);
    .send(orchestrator, tell, done(Name)).  

+finish : true <-
    updateFeed;
    .wait(feed_order(FeedList));
    !collect_messages(FeedList, "", Conversation);
    !update_affectivity(Conversation);
    .my_name(Name);
    .send(orchestrator, tell, finished(Name)).

+!initiate_affectivity : 
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
    .print("LR=", LR, " LD=", LD, " HR=", HR, " HD=", HD).

+!update_affectivity(Conversation) :     
    political_standpoint(PS) &
    demographics(D) &
    persona_description(PD) &
    love(republicans, LR) &
    love(democrats, LD) &
    hate(republicans, HR) &
    hate(democrats, HD) 
<- 
    ia.updateAffectivity(love, republicans, LR, PS, D, PD, Conversation, NewLR);
    ia.updateAffectivity(love, democrats, LD, PS, D, PD, Conversation, NewLD);
    ia.updateAffectivity(hate, republicans, HR, PS, D, PD, Conversation, NewHR);
    ia.updateAffectivity(hate, democrats, HD, PS, D, PD, Conversation, NewHD);
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
    !collect_messages(FeedList, "", Conversation);
    ia.reply(PS, D, PD, Conversation, Response);
    FeedList = [Last | _];
    comment(Last, [], [], Response).

+!collect_messages([] , Conversation, Conversation) : true <- true.

+!collect_messages([ID|Tail], Conversation, Result) : true <-
    .wait(message(ID, Author, Content, _, _));
    .concat("\n@", Author, ": ", Content, Post);
    .concat(Post, Conversation, UpdatedConversation);
    !collect_messages(Tail, UpdatedConversation, Result).