random_range_int(Min, Max, R) :-
    .random(X) &
    Y = X * (Max - Min) + Min &
    R = math.floor(Y).

initial_affectivity_non_partisan(LR, LD, HR, HD) :-
    random_range_int(0, 4, LR) &
    random_range_int(0, 4, LD) &
    random_range_int(0, 10, HR) &
    random_range_int(0, 10, HD).

initial_affectivity_republican(LR, LD, HR, HD) :-
    random_range_int(5, 10, LR) &
    random_range_int(0, 4, LD) &
    random_range_int(0, 4, HR) &
    random_range_int(0, 10, HD).

initial_affectivity_democrat(LR, LD, HR, HD) :-
    random_range_int(0, 4, LR) &
    random_range_int(5, 10, LD) &
    random_range_int(0, 10, HR) &
    random_range_int(0, 4, HD).

+!initiate_republican : 
    initial_affectivity_republican(LR, LD, HR, HD)
<-
    +love(republicans, LR);
    +love(democrats, LD);
    +hate(republicans, HR);
    +hate(democrats, HD);
    .print("LR=", LR, " LD=", LD, " HR=", HR, " HD=", HD).

+!initiate_democrat : 
    initial_affectivity_democrat(LR, LD, HR, HD)
<-
    +love(republicans, LR);
    +love(democrats, LD);
    +hate(republicans, HR);
    +hate(democrats, HD);
    .print("LR=", LR, " LD=", LD, " HR=", HR, " HD=", HD).

+!initiate_non_partisan : 
    initial_affectivity_non_partisan(LR, LD, HR, HD)
<-
    +love(republicans, LR);
    +love(democrats, LD);
    +hate(republicans, HR);
    +hate(democrats, HD);
    .print("LR=", LR, " LD=", LD, " HR=", HR, " HD=", HD).

+message(Id, Author, Content, Original, Timestamp) : 
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