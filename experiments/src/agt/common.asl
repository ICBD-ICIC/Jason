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
    ia.affectivity(
        context(PS, D, PD),
        affect(NewLR, NewLD, NewHR, NewHD));
    .print("LR=", NewLR, " LD=", NewLD, " HR=", NewHR, " HD=", NewHD);
    +love(republicans, NewLR);
    +love(democrats, NewLD);
    +hate(republicans, NewHR);
    +hate(democrats, NewHD);
    +initiation_done.

+!update_affectivity(Conversation) :     
    political_standpoint(PS) &
    demographics(D) &
    persona_description(PD) &
    love(republicans, LR) &
    love(democrats, LD) &
    hate(republicans, HR) &
    hate(democrats, HD) 
<- 
    ia.affectivity(
        affect(LR, LD, HR, HD),
        context(PS, D, PD),
        Conversation,
        affect(NewLR, NewLD, NewHR, NewHD));
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