create table users
(
    id          int auto_increment primary key,
    username    varchar(255) null,
    slack_id    varchar(255),
    my_reaction int default 5,
    avatar_url  varchar(1000) null
);


create table reactions
(
    id        int auto_increment primary key,
    year      int,
    month     int,
    to_user   int,
    from_user int,
    type      varchar(50) null,
    count     int default 0,
    FOREIGN KEY (to_user) REFERENCES users (id) ON UPDATE CASCADE,
    FOREIGN KEY (from_user) REFERENCES users (id) ON UPDATE CASCADE
);