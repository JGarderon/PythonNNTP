import socket
import errno
import types
import re
import uuid 

__Taches__ = []

class Lancer():

    def __auto__(self): 
        try: 
            global __Taches__
            while len(__Taches__)>0: 
                tache = __Taches__.pop(0) 
                if isinstance(
                    tache,
                    Taches
                ): 
                    tache = tache.resoudre() 
                if isinstance(
                    tache,
                    types.GeneratorType
                ):
                    try:
                        m = next(tache)
                        if m is not None:
                            print(*m)
                        __Taches__.append(
                            tache
                        )
                    except StopIteration:
                        pass 
                    except Exception as err:
                        print("la résolution de ", tache, "a rencontré un problème :", err) 
        except KeyboardInterrupt:
            print("!!! Demande d'extinction du script !!!") 

    def __enter__(self):
        self.__auto__() 

    def __exit__(self, *args, **kwargs):
        pass 

class Taches:

    def __new__(cls, *args, **kwargs):
        global __Taches__ 
        obj = object.__new__(
            cls 
        ) 
        __Taches__.append(
            obj
        )
        return obj

    def detacher(self):
        try: 
           while self in __Taches__:
                __Taches__.remove(
                    self
                )
        except Exception:
            print("impossible de retirer toutes les occurences de ", self) 

    def resoudre(self):
        pass     

class Serveur(Taches):

    def __init__(self, paire, classe_client):
        self.paire = list(paire)
        self.classe_client = classe_client 
        self.socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )
        self.socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        ) 
        self.socket.bind(
            paire
        )
        self.socket.setblocking(
            False
        )
        self.socket.listen(
            15
        ) 

    def resoudre(self):
        while True: 
            try:
                c, a = self.socket.accept()
                c.setblocking(
                    False
                ) 
                self.classe_client(
                    c, a 
                )
                m = "!log:Serveur:resoudre = nouveau client", c 
            except BlockingIOError:
                m = None  
            except Exception as err:
                m = "!err:Serveur:resoudre = ", err 
            finally:
                yield m 

class Tache(Taches): 

    def __init__(self, client, cmd): 
        self.client = client
        self.cmd = cmd 

    def resoudre(self): 
        yield from self.client(
            self.cmd # fonction d'écho par défaut 
        ) 

class Client(Taches):

    protocole = Tache 
    separateur = "\r\n" 

    def __init__(self, connexion, adresse): 
        self.connexion = connexion
        self.adresse = adresse
        self.tampon = "" 

    def resoudre(self):
        while True: 
            try:
                portion = self.connexion.recv(1024) 
                if portion==b"": 
                    return self.clore()
                else:
                    try:
                        self.tampon += portion.decode("utf-8")
                    except:
                        return self.clore() 
            except BlockingIOError:
                pass 
            except socket.error as err:
                yield "!err:Client:resoudre = ", err 
                return self.clore()
            finally:
                try:
                    yield self.detecter() # pas async 
                except Exception as err:
                    yield "!err:client:resoudre = ", err 
    
    def detecter(self): 
        # on n'envoie qu'une tâche à la fois 
        if self.separateur in self.tampon:
            cmd, self.tampon = self.tampon.split(
                self.separateur,
                1
            ) 
            self.protocole(
                self,
                cmd 
            ) 

    def clore(self):
        try: 
            self.connexion.close()
        except Exception:
            pass 
        self.detacher()

    def envoyer(self, m):
        try: 
            self.connexion.send(
                ("%s%s"%(
                    m,
                    self.separateur
                )).encode("utf-8")
            ) 
            return "!log:client:call = ", m
        except Exception as err: 
            self.clore()
            return "!log:client:err =", err 

    def __call__(self, m):
        yield self.envoyer(
            m
        ) 

class Routines(Taches):

    def __init__(self, liste): 
        self.liste = dict(liste) 

    def resoudre(self):
        if len(self.liste)==0:
            return self.detacher() 
        try:
            for routine_id in self.liste: 
                yield from self.liste[routine_id](
                    routine_id,
                    self 
                )
        except Exception as err:
            print("!err:routines = ", err) 
        finally: 
            __Taches__.push(
                self.resoudre
            ) 

### --- Implémentation du protocole --- 

import hashlib
import os
import glob 

class NNTP_Protocole(Tache):

    racine = "/home/julien/Développement/NNTP"

    commandes = {
        re.compile(
            "^MODE READER$",
            re.IGNORECASE
        ): "nntp_MODE_READER",
        re.compile(
            "^LIST$",
            re.IGNORECASE
        ): "nntp_LIST",
        re.compile(
            "^LIST NEWSGROUPS$",
            re.IGNORECASE
        ): "nntp_LIST_NEWSGROUPS",
        re.compile(
            "^AUTHINFO (?P<action>USER|PASS) (?P<info>[a-z0-9\_\-\.]+)$",
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

    def resoudre(self): 
        yield "!log:NNTP-Protocole:resoudre", self.cmd
        for commande in self.commandes:
            r = re.match(
                commande,
                self.cmd
            )
            if r is not None: 
                try:
                    yield from getattr(
                        self,
                        self.commandes[commande]
                    )( 
                        r
                    )  
                    return 
                except Exception as err:
                    print(err) 
                    yield from self.client(
                        "KO methode non implementee"
                    )
                    return
            else:
                yield 
        yield from self.client( 
            "KO methode non existante"
        ) 

    def nntp_MODE_READER(self, r): 
        yield from self.client( 
            "200 Server ready, posting allowed" 
        ) 

    def nntp_LIST_NEWSGROUPS(self, r): 
        yield from self.client( 
            "KO pas encore implementee" 
        )

    def nntp_LIST(self, r): 
        yield from self.client( 
            "215 list of newsgroups follows" 
        )
        with open("%s/.groupes"%self.racine,"r") as f: 
            while True: 
                ligne = f.readline().strip()  
                if ligne=="": 
                    break 
                while "\t" in ligne: 
                	ligne = ligne.replace("\t", " ")
                yield from self.client(  
                    ligne 
                ) 
        yield from self.client(
            "." 
        ) 

    def nntp_GROUP(self, r):
        groupe = r.group("groupe")
        while "." in groupe:
            groupe = groupe.replace(".","/")
            groupe = groupe.replace("//","/")
            yield
        racine = os.path.join(
            self.racine,
            groupe
        )
        if os.path.isdir(racine):
            try:
                with open("%s/.statistique"%racine,"r") as f:
                    etat, nbre, mini, maxi, groupe = f.readline().strip().split("\t")
                self.client.groupe = groupe
                self.client.racine = racine
                yield from self.client( 
                    "211 %s %s %s %s"%( 
                        nbre,
                        mini,
                        maxi,
                        groupe
                    ) 
                )
            except:
                yield from self.client( 
                    "411 groupe indisponible" 
                ) 
        else: 
            yield from self.client( 
                "411 No such newsgroup" 
            ) 

    def nntp_XOVER_RANGE(self, r):
        if not hasattr(self.client, "groupe"):
            yield from self.client(
                "412 No newsgroup selected"
            )
            return 
        mini = int(r.group("mini"))
        maxi = int(r.group("maxi"))+1
        yield from self.client(
            "224 Overview information follows" 
        ) 
        for i in range(mini, maxi):
            path = "%s/%s.message"%(
                self.client.racine,
                i
            )
            if os.path.isfile(
                path
            ): 
                with open(path, "r") as f:
                    yield from self.client(
                        f.readline().strip() 
                    )
            else:
                yield 
        yield from self.client( 
            "." 
        )

    def nntp_ARTICLE(self, r): 
        yield from self.client(
            "non implemente"
        ) 

    def nntp_ARTICLE_NUMERO(self, r):
        if not hasattr(self.client, "groupe"):
            yield from self.client(
                "412 No newsgroup selected"
            ) 
        try:
            article_num = r.group("article")
            path = "%s/%s.message"%(
                self.client.racine,
                article_num
            )
            yield from self.recuperer_article(
                path
            )
        except Exception: 
            yield from self.client(
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
            yield from self.recuperer_article(
                os.path.join( 
                    self.racine, 
                    chemin 
                ) 
            ) 
        except Exception: 
            yield from self.client(
                "430 No article with that id" 
            ) 

    def recuperer_article(self, path): 
        with open(path, "r") as f: 
            numero, sujet, expediteur, date, article_id1, article_id2, taille, lignes, *reste = f.readline().strip().split("\t") 
            yield from self.client( 
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
                    yield from self.client( 
                       ligne 
                    )
            yield from self.client(
                "."  
            ) 

    def nntp_AUTHINFO(self, r):
        # 481 Authentication failed/rejected 
        # 502 Command unavailable 
        action = r.group("action").lower()
        if action=="user":
            self.client.utilisateur = r.group("info")
            yield from self.client(
                "381 Password required" 
            )
        elif action=="pass":
            if not hasattr(self.client, "utilisateur"):
                yield from self.client(
                    "482 Authentication commands issued out of sequence" 
                )
                return 
            else:
                self.client.mdp = r.group("info")
                yield from self.client(
                    "281 Authentication accepted" 
                )

    def nntp_POST(self, r): 
        yield from self.client(
            "340 Input article; end with <CR-LF>.<CR-LF>" 
        )
        try:
            cherche = re.compile(
                "(?P<motif>\r|\r\n|\n)\.(?P=motif)"
            ) 
            while True:
                r = cherche.search( 
                    self.client.tampon
                ) 
                if r is None: 
                    yield
                else: 
                    cherche = "%s.%s"%(
                        (r.group("motif"),)*2 
                    ) 
                    message, self.client.tampon = self.client.tampon.split( 
                        cherche, 
                        1 
                    ) 
                    tmp_uuid = uuid.uuid4() 
                    with open(
                        "%s/tmp/message-%s.tmp"%(
                            self.racine, 
                            tmp_uuid 
                        ), 
                        "w"
                    ) as f:
                        f.write(
                            message
                        )
                        self.client.enregistrement = False
                    break 
            yield from self.client(
                "240 Article received OK" 
            ) 
        except Exception as err:
            self.client.enregistrement = False 
            print("post ko ; err = ", err)  
            yield from self.client(
                "441 Posting failed" 
            ) 

    def nntp_QUIT(self, r): 
        yield from self.client(
            "205 Connection closing" 
        )
        self.deconnecter() 
        
        
    def verifier(self, cmd_id="*", envoi=True):
        if self.client.connecte is not True:
            if envoi is True:
                self.client.envoyer(
                    cmd_id,
                    "KO Non connecte" 
                ) 
            return False 
        return True 

    def deconnecter(self): 
        self.client.connecte = False
        try:
            del self.client.path 
            del self.client.pseudo 
        except Exception:
            pass
        finally:
            self.detacher() 
        

class NNTP_Client(Client):

    protocole = NNTP_Protocole
    exception_cmd = re.compile( 
        "^POST",
        re.IGNORECASE 
    ) 

    def __init__(self, connexion, adresse):
        super().__init__(
            connexion,
            adresse
        )
        self.enregistrement = False 
        self.connecte = False 
        self.envoyer(
            "200 jacoboni InterNetNews server INN 2.2 21-Jan-1999 ready"
        )

    def detecter(self): 
        if self.enregistrement is False: 
            r = re.match(
                self.exception_cmd,             
                self.tampon 
            ) 
            super().detecter()
            if r is not None:
                self.enregistrement = True 

### --- Main() --- 

Serveur(
    (
        "127.0.0.1",
        8119 
    ),
    NNTP_Client  
) 

with Lancer(): 
    print("---FIN---") 



