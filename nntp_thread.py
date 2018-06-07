# coding: utf8

### Nothus, mai 2017 - juin 2018
### Julien Garderon, code non libre de droit
### julien.garderon@gmail.com / @intelligencepol sur Twitter
### JGarderon sur GitHub 

import socketserver
import errno
import types
import re
import uuid 
import hashlib
import os
import glob
import email 

class NNTP_Protocole: 

    lecteur = False 
    racineDefaut = "."

    commandes = { 
        re.compile(
            "^CAPABILITIES$",
            re.IGNORECASE
        ): "nntp_CAPABILITIES",
        re.compile(
            "^MODE READER$",
            re.IGNORECASE
        ): "nntp_MODE_READER",
        re.compile(
            "^LIST OVERVIEW.FMT$",
            re.IGNORECASE
        ): "nntp_LIST_OVERVIEWFMT",
        re.compile(
            "^LIST$",
            re.IGNORECASE
        ): "nntp_LIST",
        re.compile(
            "^LIST NEWSGROUPS$",
            re.IGNORECASE
        ): "nntp_LIST_NEWSGROUPS",
        re.compile(
            "^AUTHINFO (?P<action>USER|PASS) (?P<info>[a-z0-9\_\-\.\@]+)$",
            re.IGNORECASE
        ): "nntp_AUTHINFO",
        re.compile(
            "^GROUP (?P<groupe>[a-z0-9\.]+)$",
            re.IGNORECASE
        ): "nntp_GROUP",
        re.compile(
            "^XOVER (?P<mini>[0-9]+)\-(?P<maxi>[0-9]+)$",
            re.IGNORECASE
        ): "nntp_XOVER_RANGE",
        re.compile(
            "^ARTICLE$",
            re.IGNORECASE
        ): "nntp_ARTICLE", 
        re.compile(
            "^ARTICLE (?P<article>[0-9]+)$",
            re.IGNORECASE
        ): "nntp_ARTICLE_NUMERO", 
        re.compile(
            "^ARTICLE \<(?P<articleId>[0-9a-z\-\_]+)(\@(?P<domaine>[^\s\>]*))\>$",
            re.IGNORECASE
        ): "nntp_ARTICLE_ID", 
        re.compile(
            "^QUIT$",
            re.IGNORECASE
        ): "nntp_QUIT", 
        re.compile(
            "^POST$",
            re.IGNORECASE
        ): "nntp_POST" 
    }

    def __init__(self, client):
        self.client = client 
        self.utilisateur = None 
        self.mdp = None
        self.groupe = None
        self.racine = None 
        self.client.envoyer(
            "200 jacoboni InterNetNews server INN 2.2 21-Jan-1999 ready"
        ) 

    def resoudre(self):
        self.cmd = self.client.recevoir()
        if len(self.cmd)==0:
            self.client.stopper() 
        for commande in self.commandes:
            r = re.match( 
                commande,
                self.cmd
            )
            if r is not None: 
                try:
                    getattr(
                        self,
                        self.commandes[commande]
                    )( 
                        r
                    )  
                    return 
                except Exception as err:
                    print(err) 
                    self.client.envoyer(
                        "KO methode non implementee"
                    )
                    return

    def nntp_QUIT(self,r):
        self.client.stopper() 

    def nntp_MODE_CAPABILITIES(self, r): 
        self.client.envoyer( 
            (
                "101 Server capabilities", 
                "VERSION 2", 
                "READER", 
                "OVER", 
                "POST", 
                "LIST ACTIVE NEWSGROUPS ACTIVE.TIMES OVERVIEW.FMT", 
                "OVER MSGID", 
                "."
            ) 
        ) 

    def nntp_MODE_READER(self, r):
        self.lecteur = True 
        self.client.envoyer( 
            "200 Server ready, posting allowed" 
        )

    def nntp_LIST_OVERVIEWFMT(self, r):
        self.client.envoyer( 
            (
                "215 list of newsgroups follows", 
                "Subject:", 
                "From:", 
                "Date:", 
                "Message-ID:", 
                "References:", 
                ":bytes", 
                ":lines", 
                "." 
            ) 
        )

    def nntp_LIST_NEWSGROUPS(self, r): 
        self.client.envoyer( 
            "KO pas encore implementee" 
        )

    def nntp_LIST(self, r): 
        self.client.envoyer( 
            "215 list of newsgroups follows" 
        )
        with open(
            "%s/.groupes"%self.racine,
            "r"
        ) as f: 
            while True: 
                ligne = f.readline().strip()  
                if ligne=="": 
                    break 
                while "\t" in ligne: 
                	ligne = ligne.replace("\t", " ")
                self.client.envoyer(  
                    ligne 
                ) 
        self.client.envoyer(
            "." 
        )

    def traduire_groupe(self, groupe):
        if re.match("^([a-zA-Z0-9\.]+)$") is None:
            return False 
        while "." in groupe:
            groupe = groupe.replace(".","/")
            groupe = groupe.replace("//","/")
        return groupe 

    def nntp_GROUP(self, r):
        groupe = self.traduire_groupe(
            r.group("groupe")
        ) 
        if groupe is False:
            return self.client.envoyer( 
                "411 No such newsgroup" 
            )
        racine = os.path.join(
            self.racineDefaut+"/",
            groupe
        ) 
        if os.path.isdir(racine):
            try:
                with open("%s/.statistique"%racine,"r") as f:
                    etat, nbre, mini, maxi, groupe = f.readline().strip().split("\t")
                self.groupe = groupe
                self.racine = racine
                self.client.envoyer( 
                    "211 %s %s %s %s"%( 
                        nbre,
                        mini,
                        maxi,
                        groupe
                    ) 
                )
            except:
                self.client.envoyer( 
                    "411 groupe indisponible" 
                ) 
        else: 
            self.client.envoyer( 
                "411 No such newsgroup" 
            ) 

    def nntp_XOVER_RANGE(self, r):
        if not hasattr(self.client, "groupe"):
            self.client.envoyer(
                "412 No newsgroup selected"
            )
            return 
        mini = int(r.group("mini"))
        maxi = int(r.group("maxi"))+1
        self.client.envoyer(
            "224 Overview information follows" 
        ) 
        for i in range(mini, maxi):
            path = "%s/%s.message"%(
                self.racine,
                i
            )
            if os.path.isfile(
                path 
            ): 
                with open(path, "r") as f:
                    self.client.envoyer(
                        f.readline().strip() 
                    ) 
        self.client.envoyer( 
            "." 
        )

    def nntp_ARTICLE(self, r): 
        self.client.envoyer(
            "non implemente"
        ) 

    def nntp_ARTICLE_NUMERO(self, r):
        if not hasattr(self.client, "groupe"):
            self.client.envoyer( 
                "412 No newsgroup selected"
            ) 
        try:
            article_num = r.group("article")
            path = "%s/%s.message"%(
                self.racine,
                article_num
            ) 
            self.recuperer_article(
                path
            )
        except Exception as err: 
            self.client.envoyer(
                "423 No article with that number" 
            )

    def nntp_ARTICLE_ID(self, r):
        try:
            articleId_chemin = "%s/ids/message-%s.id"%( 
                self.racine, 
                r.group("articleId") 
            ) 
            with open(articleId_chemin, "r") as f: 
                chemin = f.read().strip() 
            self.recuperer_article(
                os.path.join( 
                    self.racine, 
                    chemin 
                ) 
            ) 
        except Exception: 
            self.client.envoyer(
                "430 No article with that id" 
            ) 

    def recuperer_article(self, path): 
        with open(path, "r") as f: 
            numero, sujet, expediteur, date, article_id1, *reste = f.readline().strip().split("\t") 
            self.client.envoyer( 
                "220 %s %s"%( 
                    numero,
                    article_id1
                ) 
            ) 
            while True:
                ligne = f.readline()
                if ligne=="":
                    break
                else:
                    ligne = ligne.strip() 
                    if ligne==".":
                        ligne = ".." 
                    self.client.envoyer( 
                       ligne 
                    )
            self.client.envoyer(
                "."  
            ) 

    def nntp_AUTHINFO(self, r):
        # 481 Authentication failed/rejected 
        # 502 Command unavailable 
        action = r.group("action").lower()
        if action=="user":
            self.utilisateur = r.group("info")
            self.client.envoyer(
                "381 Password required" 
            )
        elif action=="pass":
            if not hasattr(self, "utilisateur"):
                self.client.envoyer(
                    "482 Authentication commands issued out of sequence" 
                )
                return 
            else:
                self.mdp = r.group("info")
                self.client.envoyer(
                    "281 Authentication accepted" 
                )

    def nntp_POST(self, r): 
        self.client.envoyer(
            "340 Input article; end with <CR-LF>.<CR-LF>" 
        )
        try:
            chemin = False
            tampon = "" 
            while True: 
                self.client.debug = False 
                portion = self.client.recevoir() 
                if portion==".":
                    e = email.message_from_string(tampon)
                    for nom, valeur in e._headers: 
                        if nom.lower()=="newsgroups":
                            chemin = self.traduire_groupe(
                                valeur
                            )
                    if chemin==False: 
                        return self.client.envoyer( 
                            "441 no valid group" 
                        ) 
                    if not os.path.isdir(
                        "%s/%s"%(
                            self.racineDefaut,
                            chemin
                        ) 
                    ): 
                        return self.client.envoyer( 
                            "441 group no exists" 
                        ) 
                    tmp_uuid = uuid.uuid4()
                    with open( 
                        "./tmp/message-%s.tmp"%( 
                            tmp_uuid 
                        ), 
                        "w" 
                    ) as f:
                        f.write( 
                            tampon  
                        ) 
                    break 
                else: 
                    tampon += portion+"\n" 
            self.client.debug = True 
            self.client.envoyer( 
                "240 Article received OK" 
            ) 
        except Exception as err: 
            print("post ko ; err = ", err)  
            self.client.envoyer(
                "441 Posting failed" 
            ) 

class NNTP_Client(socketserver.StreamRequestHandler): 

    objProtocole = None
    continuer = True

    debug = True 

    def envoyer(self, m):
        if isinstance(m, str): 
            m = (m,)
        for ligne in m:
            if self.debug:
                print("<<<\t", ligne) 
            self.wfile.write(
                (ligne.strip()+"\r\n").encode("utf-8") 
            ) 

    def recevoir(self):
        ligne = self.rfile.readline().decode("utf-8").strip() 
        if self.debug:
            print(">>>\t", ligne) 
        return ligne

    def stopper(self):
        self.continuer = False 

    def handle(self): 
        if self.debug:
            print("arrivé d'un nouveau client") 
        self.objProtocole = NNTP_Protocole( 
            self 
        ) 
        while self.continuer: 
            self.objProtocole.resoudre() 
        if self.debug:
            print("départ d'un client") 
            
        

if __name__ == "__main__":
    HOST, PORT = "localhost", 9999

    with socketserver.TCPServer((HOST, PORT), NNTP_Client) as server:
        server.serve_forever() 
