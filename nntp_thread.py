# coding: utf8

### Nothus, mai 2017 - juin 2018
### Julien Garderon, code non libre de droit
### julien.garderon@gmail.com / @intelligencepol sur Twitter
### JGarderon sur GitHub 

import sys 
import socketserver
import errno
import types
import re
import uuid 
import hashlib
import os
import glob
import email
import time 
from datetime import date 
import datetime 
import fnmatch 
import math 

### ### ### ### ### ### ### ### ###

#!# Création du fichier log et de toutes les fonctions associées 
import logging

LOG_FORMAT_COURT = '%(asctime)s | %(levelname)s - %(thread)d - %(message)s' 
LOG_FORMAT_LONG = '%(asctime)s | %(levelname)s - %(process)d::%(processName)s::%(thread)d - %(name)s - %(message)s' 
logging.basicConfig(
    level=logging.DEBUG,
    format=LOG_FORMAT_LONG,
    datefmt='%m-%d %H:%M',
    filename="./.log", 
    filemode='w' 
)
console = logging.StreamHandler()
console.setLevel(
    logging.DEBUG
) 
console.setFormatter(
    logging.Formatter(
        LOG_FORMAT_COURT 
    )
)
logging.getLogger(
    ''
).addHandler( 
    console
)

logging.debug("/!-début\ démarrage des logs")
logging.info("démarrage du script")

### ### ### ### ### ### ### ### ###

#!# Ces deux variables permettent d'indiquer l'absence de service
### disponible et ce malgré la connexion réussie du client. En
### dehors de certaines étapes de maintenance lourdes, ces états
### du serveur n'ont que peu d'intérêt. 
NNTP_SERVEUR_INDISPONIBLE_PERMANENCE = False
NNTP_SERVEUR_INDISPONIBLE_TEMPORAIRE = False 

### ### ### ### ### ### ### ### ###

#!# La signature de reconnaissance du serveur
### Script initial mai 2017 
### Version 0.0.1 / démarrage du projet : 07 juin 2018 
### Version 0.0.2 : 08 juin 2018
### Version 0.0.3 : 11 juin 2018
### Version 0.0.4 : 12 juin 2018
### Version 0.0.5 : 13 juin 2018 
NNTP_SERVEUR_SIGNATURE = "nothus 0.0.5 nntp server"

### ### ### ### ### ### ### ### ###

#!# Le verrou en "lecture seule" renvoie le code 201
### au lieu de 200. Il a pour sens d'indiquer l'impossibilité
### absolue pour le serveur d'accepter une écriture venant
### de l'extérieur. Ceci n'a pas de rapport avec les permissions
### individuelles des groupes et des utilisateurs. 
VERROU_LECTURE_SEULE = True

### ### ### ### ### ### ### ### ###

NNTP_UTILISATEURS_SOURCE = "./utilisateurs" 
NNTP_MESSAGES_SOURCE = "./sources" 
NNTP_MESSAGES_EXT = "contenu" 
NNTP_MESSAGE_EXT = "message" 
NNTP_MESSAGE_REF_EXT = "reference" 
NNTP_GROUPES_ARBORESCENCE = "./.groupes" 
NNTP_GROUPES_SOURCES = "."
NNTP_GROUPE_STATISTIQUE = ".statistique" 
NNTP_MESSAGES_ANNUAIRE = ".annuaire" 

### ### ### ### ### ### ### ### ### 

#!# Création de quelques fichiers indipensables... 
if not os.path.isfile( 
    NNTP_GROUPES_ARBORESCENCE
): 
    logging.info(
        "Création du fichier des groupes '%s'" % NNTP_GROUPES_ARBORESCENCE 
    ) 
    with open( 
        NNTP_GROUPES_ARBORESCENCE,
        "w"
    ) as f:
        f.write( 
            "\t".join( 
                (
                    "nothus", 
                    "0", 
                    "0", 
                    "0", 
                    "n", 
                    str( 
                        math.floor( 
                            time.time()
                        ) 
                    ), 
                    "La racine du service" 
                )
            )
        )

### ### ### ### ### ### ### ### ###

#!# Les entêtes supplémentaires gérés par le serveur.
### Les entêtes supplémentaires doivent tous être
### associés avec la mention ":full" (RFC 3977). 
NNTP_MESSAGE_ENTETES_SUPP = [ 
    entete+":full" for entete in [ 
        "Resume", 
        "Newsgroups", 
        "Organization", 
        "Publication" 
    ] 
] 

### ### ### ### ### ### ### ### ###

#!# Les fonctions essentielles, pour faire le lien entre le protocole
### et le SGBD qui gère concrétement les messages. A noter que
### l'implémentation par défaut, celle développée ici, s'appuye sur
### le système de fichiers (c-à-d un SGBD "plat"). 

def utilisateur_hasher(courriel, mdp): 
    """
        Ici les fonctions utilisées pour "hasher" les courriels / mdp,
        indépendamment de l'implémentation même du protocole. 
    """
    cId = hashlib.sha256(
        courriel.encode("utf-8") 
    ).hexdigest() 
    pId = hashlib.sha256(
        (courriel+mdp).encode("utf-8") 
    ).hexdigest() 
    return cId, pId 

def utilisateur_creer(courriel, mdp): 
    """
        La fonction permet aussi bien de créer un nouvel utilisateur,
        que d'écraser un utilisateur existant (changement de mot de passe
        par exemple). 
    """
    try:
        cId, pId = utilisateur_hasher(
            courriel,
            mdp 
        ) 
        with open( 
            "%s/%s.utilisateur"%(
                NNTP_UTILISATEURS_SOURCE,
                cId
            ),
            "w" 
        ) as f:
            f.write(
                pId
            )
        return True
    except Exception as err: 
        logging.ERROR(
            "[BDD] utilisateur::creer '%s' impossible : %s" % (
                courriel,
                err
            ) 
        ) 
        return False
    
def utilisateur_verifier(courriel, mdp):
    """
        Savoir si un client qui s'authentifie, correspond bien à un
        utilisateur ou non. 
    """ 
    try:
        cId, pId = utilisateur_hasher(
            courriel,
            mdp 
        ) 
        with open( 
            "%s/%s.utilisateur"%(
                NNTP_UTILISATEURS_SOURCE,
                cId
            ),
            "r" 
        ) as f: 
            passe = f.readline().strip() 
            if passe==pId:
                logging.info(
                    "utilisateur %s authentifié" % courriel
                ) 
                return cId
        return False
    except Exception as err: 
        logging.ERROR(
            "[BDD] utilisateur::verifier '%s' impossible : %s" % (
                courriel,
                err
            ) 
        )
        return False
    
def groupe_traduire(groupe): 
    if re.match("^([a-zA-Z0-9\.]+)$", groupe) is None:
        return False 
    while "." in groupe:
        groupe = groupe.replace(".","/")
        groupe = groupe.replace("//","/")
    return groupe 

def groupe_existe(groupe, traduire_groupe=True):
    if traduire_groupe: 
        pathGroupe = groupe_traduire( 
            groupe
        )
    else:
        pathGroupe = groupe
    if pathGroupe is False: 
        return False
    racine = os.path.join(
        NNTP_GROUPES_SOURCES+"/", 
        pathGroupe  
    ) 
    if not os.path.isdir(
        racine 
    ): 
        return False
    return (
        groupe,
        racine
    ) 

def groupe_statistiques(pathGroupe):
    with open( 
        "%s/%s" % (
            pathGroupe,
            NNTP_GROUPE_STATISTIQUE
        ), 
        "r", 
        encoding="utf-8" 
    ) as f: 
        return f.readline().strip().split("\t")

def groupe_lister(groupe, traduire_groupe=True):  
    if traduire_groupe: 
        pathGroupe = groupe_traduire( 
            groupe
        )
    else:
        pathGroupe = groupe 
    with open( 
        "%s/%s" % ( 
            pathGroupe, 
            NNTP_MESSAGES_ANNUAIRE 
        ), 
        "r", 
        encoding="utf-8" 
    ) as f:
        while True: 
            ligne = f.readline()
            if ligne=="":
                break
            yield ligne.strip().split("\t") 

def article_chercher_id(numero, groupe="", traduire_groupe=True):
    numero = int(numero) 
    for message in groupe_lister(
        groupe,
        traduire_groupe
    ):
        if numero==int(message[0]):
            return (message[1], numero)
    return (False, numero) 

def article_chercher_numero(aId, groupe="", traduire_groupe=True): 
    for message in groupe_lister(
        groupe,
        traduire_groupe
    ):
        if aId==message[1]:
            return (aId, int(message[0]))
    return False

def article_traduire_id(aId, extraire=True):
    try:
        if extraire:
            return re.match( 
                "\<([^\@\>]+)\@[a-z0-9\.]+\>$", 
                aId
            ).groups()[0] 
    except Exception as err:
        logging.ERROR(
            "[BDD] article::traduireId impossible : %s" % err 
        )
    return False 

def article_recuperer(path, articleNumero, articleId, entete=True, corps=True):
    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:
        f.readline() 
        partieLue = 0 
        while True:
            ligne = f.readline()
            envoi = False 
            if ligne=="":
                break
            elif partieLue==0 and ligne=="\n":
                partieLue = 1 
            else: 
                ligne = ligne.strip() 
                if ligne==".": 
                    ligne = ".." 
            if entete and partieLue<1: 
                envoi = True 
            elif corps and partieLue>0: 
                envoi = True
            elif corps is False and partieLue>0:
                break 
            if envoi: 
                yield ligne 

def groupes_lister(wm=None):
    # path nbre mini maxi publier dateCreation 
    with open(
        NNTP_GROUPES_ARBORESCENCE,
        "r",
        encoding="utf-8" 
    ) as f: 
        while True: 
            ligne = f.readline().strip()  
            if ligne=="": 
                break
            yield ligne.split("\t") 

### ### ### ### ### ### ### ### ### 

class NNTP_Protocole: 

    lecteur = False 
    racineDefaut = "./"

    commandes = {
        
        # Commandes d'état 
        re.compile(
            "^CAPABILITIES$",
            re.IGNORECASE
        ): "nntp_CAPABILITIES",
        re.compile(
            "^MODE READER$",
            re.IGNORECASE
        ): "nntp_MODE_READER",
        re.compile(
            "^AUTHINFO (?P<action>USER|PASS) (?P<info>[a-z0-9\_\-\.\@]+)$",
            re.IGNORECASE
        ): "nntp_AUTHINFO",
        re.compile(
            "^QUIT$",
            re.IGNORECASE
        ): "nntp_QUIT",
        
        # Commandes d'entêtes
        re.compile(
            "^LIST OVERVIEW.FMT$",
            re.IGNORECASE 
        ): "nntp_LIST_OVERVIEWFMT", 
        
        # Commandes de listes et de groupes 
        re.compile(
            "^LIST$",
            re.IGNORECASE
        ): "nntp_LIST", 
        re.compile(
            "^LIST NEWSGROUPS$", 
            re.IGNORECASE
        ): "nntp_LIST_NEWSGROUPS", 
        re.compile(
            "^LIST NEWSGROUPS(?P<wildmat> [a-z\.\?\*\,]+)?$", 
            re.IGNORECASE
        ): "nntp_LIST_NEWSGROUPS_WILDMAT", 
        re.compile(
            "^NEWGROUPS(?P<wildmat> [a-z\.\?\*\,]+)? (?P<date>[0-9]{6,8}) (?P<heure>[0-9]{6})(?P<gmt>\ GMT)?$", 
            re.IGNORECASE
        ): "nntp_NEWGROUPS", 
        re.compile(
            "^NEWNEWS(?P<wildmat> [a-z\.\?\*\,]+)? (?P<date>[0-9]{6,8}) (?P<heure>[0-9]{6})(?P<gmt>\ GMT)?$", 
            re.IGNORECASE
        ): "nntp_NEWNEWS", 
        re.compile(
            "^GROUP (?P<groupe>[a-z0-9\.]+)$", 
            re.IGNORECASE
        ): "nntp_GROUP", 

        # Commande de récupération de portion de groupe 
        re.compile(
            "^(?P<x>X)?OVER (?P<mini>[0-9]+)\-(?P<maxi>[0-9]+)$", 
            re.IGNORECASE
        ): "nntp_XOVER_RANGE", 
        
        # Commandes de récupération de contenus et de statistiques 
        re.compile(
            "^(?P<partie>ARTICLE|HEAD|BODY|STAT)$",
            re.IGNORECASE
        ): "nntp_PARTIE", 
        re.compile(
            "^(?P<partie>ARTICLE|HEAD|BODY|STAT) (?P<article>[0-9]+)$",
            re.IGNORECASE
        ): "nntp_PARTIE_NUMERO", 
        re.compile(
            "^(?P<partie>ARTICLE|HEAD|BODY|STAT) (?P<uri>\<(?P<articleId>[0-9a-z\-\_]+)(\@(?P<domaine>[^\s\>]*))\>)$",
            re.IGNORECASE
        ): "nntp_PARTIE_ID", 
        
        # Commandes de publication 
        re.compile(
            "^POST$", 
            re.IGNORECASE
        ): "nntp_POST",

        # Commandes d'informations 
        re.compile(
            "^DATE$",
            re.IGNORECASE
        ): "nntp_DATE", 
        re.compile(
            "^HELP$",
            re.IGNORECASE
        ): "nntp_HELP" 
        
    }

    def __init__(self, client):
        self.client = client 
        self.utilisateur = None 
        self.mdp = None 
        self.groupe = None 
        self.racine = None 
        if NNTP_SERVEUR_INDISPONIBLE_PERMANENCE:
            self.client.envoyer(
                "502 server permanently unavailable"
            )
            self.client.stopper() 
        elif NNTP_SERVEUR_INDISPONIBLE_TEMPORAIRE:
            self.client.envoyer(
                "400 server temporarily unavailable"
            )
            self.client.stopper() 
        else: 
            self.client.envoyer(
                "%s %s ready"%(
                    (
                        201 if VERROU_LECTURE_SEULE==True else 200 
                    ), 
                    NNTP_SERVEUR_SIGNATURE
                ) 
            ) 

    def resoudre(self):
        self.cmd = self.client.recevoir()
        if self.cmd is False:
            return 
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

    def envoyer_article(self, aNum, aId, entete=True, corps=True): 
        path = "%s/%s.%s" % ( 
            NNTP_MESSAGES_SOURCE, 
            aId, 
            NNTP_MESSAGES_EXT 
        ) 
        self.client.envoyer( 
            "220 %s %s"%( 
                aNum,
                aId
            ) 
        )
        for ligne in article_recuperer(
            path,
            articleNumero,
            articleId,
            entete, corps
        ):
            self.client.envoyer(
                ligne
            ) 
        self.client.envoyer( 
            "." 
        )
        return path 

    def nntp_CAPABILITIES(self, r):
        """     Commande "CAPABILITIES"
        -> interroge le serveurs sur ses capacités et les
        fonctions qu'il offre 
        """
        #TODO# antémémoire à corriger ici
        self.client.envoyer(
            "101 server capabilities"
        ) 
        if VERROU_LECTURE_SEULE:
            self.client.envoyer(
                ( 
                    "VERSION 2", 
                    "READER", 
                    "LIST ACTIVE NEWSGROUPS", 
                    "." 
                ) 
            )
        else: 
            self.client.envoyer( 
                ( 
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
        """     Commande "MODE READER"
        -> permet d'indiquer un mode serveur-client
        
        nb : le cas d'un retour 502 est improbable malgré son
        ajout dans la RCF : dès la connexion au serveur,
        en cas d'indisponibilité permanente confirmée
        dans les paramêtres, la connexion est coupée
        après l'information du client... 
        """
        if NNTP_SERVEUR_INDISPONIBLE_PERMANENCE:
            self.client.envoyer(
                "502 server permanently unavailable"
            ) 
            self.client.stopper()
        else: 
            self.lecteur = True 
            self.client.envoyer( 
                "%s Server ready, posting %s allowed"%(
                    (
                        201 if VERROU_LECTURE_SEULE==True else 200 
                    ), 
                    (
                        "not" if VERROU_LECTURE_SEULE==True else "" 
                    ) 
                )  
            )

    def nntp_QUIT(self,r):
        """     Commande "QUIT"
        -> permet la connexion "propre" d'une client, après
        signalement
        """ 
        self.client.envoyer(
            "205 connection will be closed immediatly" 
        ) 
        self.client.stopper() 
    
    def nntp_LIST_OVERVIEWFMT(self, r):
        """     Commande "LIST OVERVIEW.FMT"
        -> indique les entêtes gérés et exploitables par le
        serveur, en fonction des besoins d'informations du
        client.

        nb :
        - les 7 premiers champs sont réservés par la RFC et
        ne sont pas exploitables pour une extension privée ;
        - le programme ci-présent permet nativement d'étendre
        l'indexation et la recherche à de nouveaux entêtes. 
        """
        lignes = [
            "215 list of newsgroups follows", 
            "Subject:", 
            "From:", 
            "Date:", 
            "Message-ID:", 
            "References:", 
            ":bytes", 
            ":lines", 
        ]+NNTP_MESSAGE_ENTETES_SUPP+[
            ".", 
        ]
        self.client.envoyer( 
            lignes  
        )

    def nntp_LIST(self, r): 
        """     Commande "LIST"
        -> c'est la commande principale pour récupérer la liste des
        groupes disponibles sur le serveur.

        nb : c'est la seule commande de listage qui n'utilise ni limite
        ni classement notable. 
        """ 
        self.client.envoyer( 
            "215 list of newgroups follows" 
        )
        for groupe in groupes_lister():
            nom, nbre, minNum, maxNum, publier, dateCrea, description = groupe 
            self.client.envoyer(  
                " ".join(
                    ( 
                        nom, 
                        maxNum,
                        minNum,
                        publier
                    ) 
                ) 
            ) 
        self.client.envoyer(
            "." 
        ) 

    def nntp_LIST_NEWSGROUPS(self, r):
        """     Commande "LIST NEWSGROUPS"
        -> liste tous les groupes en indiquant le noms "humains"
        (une courte description) de chacun d'entre eux, sans aucun
        tri ou aucune limitation. 

        nb : cela ne préjuge pas que la liste soit complète au 
        moment de la transmission (cf RFC). 
        """
        lignes = [ 
            "215 list of newgroups follows",  
        ]
        for groupe in groupes_lister():
            lignes.append( 
                "%s %s"%(
                    nom,
                    description 
                ) 
            ) 
        lignes.append( 
            "." 
        ) 
        self.client.envoyer( 
            lignes 
        ) 

    def nntp_LIST_NEWSGROUPS_WILDMAT(self, r):
        """     Commande "LIST NEWSGROUPS (+wildmat)"
        -> filtre les groupes en fonction d'un pattern wildmat 
        fourni par le client, afin de récupérer le noms "humains"
        de chaque groupe (une courte description). 

        nb : cela ne préjuge pas que la liste soit complète au 
        moment de la transmission (cf RFC). 
        """
        lignes = [ 
            "215 list of newgroups follows",  
        ]
        w = r.group("wildmat") 
        if w is not None:
            w = w.strip() 
        for groupe in groupes_lister():
            etat = True 
            nom, nbre, minNum, maxNum, publier, dateCrea, description = groupe
            if w is not None: 
                if not fnmatch.fnmatch( 
                    nom,
                    w  
                ): 
                    etat = False 
            if etat: 
                lignes.append( 
                    "%s %s"%(
                        nom,
                        description 
                    ) 
                ) 
                
        lignes.append( 
            "." 
        ) 
        self.client.envoyer( 
            lignes 
        ) 

    def nntp_NEWGROUPS(self, r): 
        """     Commande "NEWGROUPS"
        -> permet la récupération des nouveaux groupes, avec la possibilité
        de restriction de leur nom, et qui ont été créé à partir d'une 
        date fournie par le client. 

        nb : cela ne préjuge pas que la liste soit complète au 
        moment de la transmission (cf RFC). 
        """ 
        wildmat, vouluDate, vouluHeure, vouluGMT = r.groups() 
        if wildmat is not None: 
            wildmat = wildmat.strip().split(",") 
        vouluGMT = False if vouluGMT is None else True 
        tempsVoulu = datetime.datetime.strptime( 
            "%s%s"%(
                vouluDate,
                vouluHeure
            ),
            "%Y%m%d%H%M%S" 
        )
        lignes = [ 
            "231 list of newgroups follows",  
        ] 
        for groupe in groupes_lister(): 
            nom, nbre, minNum, maxNum, publier, dateCrea, description = groupe 
            dateCrea = datetime.datetime.fromtimestamp( 
                int( 
                    dateCrea 
                ) 
            ) 
            if dateCrea>=tempsVoulu: 
                if wildmat is not None: 
                    for w in wildmat:
                        if fnmatch.fnmatch( 
                            groupe,
                            w
                        ): 
                            lignes.append( 
                                " ".join( 
                                    ( 
                                        nom, 
                                        maxNum, 
                                        minNum, 
                                        publier 
                                    ) 
                                ) 
                            ) 
                            break 
                else: 
                    lignes.append( 
                        " ".join( 
                            ( 
                                nom, 
                                maxNum, 
                                minNum, 
                                publier 
                            ) 
                        ) 
                    ) 
                    
        lignes.append( 
            "." 
        ) 
        self.client.envoyer( 
            lignes 
        ) 

    def nntp_NEWNEWS(self, r):
        """     Commande "NEWNEWS"
        -> permet la récupération des nouveaux messages, avec la possibilité
        de restriction de noms de groupe, et qui ont été créé à partir d'une
        date fournie par le client. 

        nb : cela ne préjuge pas que la liste soit complète au 
        moment de la transmission (cf RFC). 
        """ 
        wildmat, vouluDate, vouluHeure, vouluGMT = r.groups() 
        if wildmat is not None: 
            wildmat = wildmat.strip().split(",") 
        vouluGMT = False if vouluGMT is None else True 
        tempsVoulu = datetime.datetime.strptime( 
            "%s%s"%( 
                vouluDate, 
                vouluHeure 
            ), 
            "%Y%m%d%H%M%S" 
        ) 
        lignes = [ 
            "230 list of new articles by message-id follows", 
        ] 
        with open( 
            "%s/.statistique" % NNTP_MESSAGES_SOURCE, 
            "r" 
        ) as f: 
            aId, aGroupe, aDate = f.readline().strip().split("\t") 
            dateCrea = datetime.datetime.fromtimestamp( 
                int(
                    aDate
                ) 
            ) 
            if dateCrea>=tempsVoulu: 
                if wildmat is not None: 
                    for w in wildmat:
                        if fnmatch.fnmatch(
                            aGroupe,
                            w
                        ): 
                            lignes.append( 
                                "<%s@nothus.fr>" % aId 
                            ) 
                            break
                else: 
                    lignes.append( 
                        "<%s@nothus.fr>" % aId 
                    )
        lignes.append( 
            "." 
        ) 
        self.client.envoyer( 
            lignes 
        ) 

    def nntp_GROUP(self, r):
        """     Commande "GROUP"
        -> indique au serveur le groupe sur lequel le client travaille.

        nb: le fichier statistique "écrase" la valeur par défaut le nom
        du groupe, sans en changer la racine. 
        """
        r = groupe_existe( 
            r.group("groupe")
        ) 
        if r is False:
            return self.client.envoyer( 
                "411 No such newsgroup" 
            )
        groupe, racine = r 
        try: 
            etat, nbre, mini, maxi, groupe = groupe_statistiques(
                racine
            )
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
        except Exception as err: 
            print(err) 
            self.client.envoyer( 
                "411 groupe indisponible" 
            ) 

    def nntp_XOVER_RANGE(self, r):
        if not hasattr(self, "groupe"):
            self.client.envoyer(
                "412 No newsgroup selected"
            )
            return 
        mini = int(r.group("mini"))
        maxi = int(r.group("maxi")) 
        self.client.envoyer(
            "224 Overview information follows" 
        ) 
        for message in groupe_lister(
            self.racine,
            traduire_groupe=False
        ):
            mNumero = int(
                message[0]
            ) 
            if mNumero>=mini and mNumero<=maxi:
                self.client.envoyer(
                    "\t".join(
                        [
                            message[0],
                            *message[2:]
                        ]
                    ) 
                ) 
        self.client.envoyer( 
            "." 
        ) 
    
    def nntp_PARTIE(self, r):
        partie = r.group("partie").lower()
        if partie=="article":
            pass 
        elif partie=="head":
            pass 
        elif partie=="body":
            pass 
        elif partie=="stat":
            pass
        self.client.envoyer(
            "non implemente"
        ) 
        
    def nntp_PARTIE_NUMERO(self, r):
        partie = r.group("partie").lower()
        if partie=="article": 
            self.nntp_ARTICLE_NUMERO( 
                r
            ) 
        elif partie=="head":
            self.nntp_ARTICLE_NUMERO( 
                r,
                entete=True,
                corps=False 
            ) 
        elif partie=="body":
            self.nntp_ARTICLE_NUMERO( 
                r, 
                entete=False,
                corps=True 
            ) 
        elif partie=="stat":
            self.nntp_STAT_NUMERO( 
                r
            ) 
        
    def nntp_PARTIE_ID(self, r):
        partie = r.group("partie").lower() 
        if partie=="article": 
            self.nntp_ARTICLE_ID(
                r
            ) 
        elif partie=="head":
            self.nntp_ARTICLE_ID(
                r,
                entete=True,
                corps=False 
            ) 
        elif partie=="body":
            self.nntp_ARTICLE_ID(
                r, 
                entete=False,
                corps=True 
            ) 
        elif partie=="stat":
            self.nntp_STAT_ID(
                r
            ) 

    def nntp_ARTICLE(self, r): 
        if not hasattr(self.client, "groupe"): 
            self.client.envoyer( 
                "412 No newsgroup selected"
            ) 
        self.client.envoyer(
            "non implemente"
        ) 

    def nntp_ARTICLE_NUMERO(self, r, entete=True, corps=True):
        if not hasattr(self, "groupe"):
            self.client.envoyer( 
                "412 No newsgroup selected"
            ) 
        try:
            aId, aNum = article_chercher_id(
                r.group("article"),
                self.racine,
                traduire_groupe=False
            ) 
            self.envoyer_article( 
                aNum, 
                aId 
            ) 
            self.articleNumero = aNum 
        except Exception as err: 
            print(err) 
            self.client.envoyer(
                "423 No article with that number" 
            )

    def nntp_ARTICLE_ID(self, r, entete=True, corps=True):
        try:
            aId, aNum = article_chercher_numero(
                r.group("articleId"),
                groupe = self.racine,
                traduire_groupe = False
            ) 
            self.envoyer_article( 
                0 if aNum is False else aNum, 
                r.group("uri"), 
                entete, 
                corps 
            ) 
        except Exception: 
            self.client.envoyer(
                "430 No article with that id" 
            ) 

    def nntp_AUTHINFO(self, r): 
        try: 
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
                    self.cId = utilisateur_verifier(
                        self.utilisateur,
                        r.group("info") 
                    ) 
                    if self.cId is not False: 
                        self.client.envoyer(
                            "281 Authentication accepted" 
                        ) 
                    else: 
                        self.client.envoyer( 
                            "481 Authentication failed/rejected" 
                        ) 
        except Exception as err: 
            self.client.envoyer( 
                "502 Command unavailable" 
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
                            print(valeur) 
                            chemin = groupe_traduire(
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

    def nntp_DATE(self, r):
        """     Commande "DATE"
        -> signale le temps coordonné universel (UTC) du
        point de vue du serveur 
        Le protocole prévu par la RFC 3977, prévoit que cette 
        commande soit déclaré implicitement avec la capacité
         annoncée "READER". 
        """ 
        self.client.envoyer(
            "111 %s"%time.strftime( 
                "%Y%m%d%H%M%S", 
                time.gmtime() 
            ) 
        ) 

    def nntp_HELP(self, r):
        """     Commande "HELP"
        -> renvoie un texte d'aide  
        """ 
        self.client.envoyer(
            (
                "100 help text follows",
                "... no text for now ...",
                "."
            ) 
        ) 

    def nntp_STAT(self, r):
        # 223 numero id article exists 
        # 412 no group selected 
        # 420 (groupe vide) 
        pass 

    def nntp_STAT_NUMERO(self, r):
        # 223 numero id article exists 
        # 412 no group selected 
        # 423 no article with this numero
        pass 

    def nntp_STAT_ID(self, r): 
        # 223 0|numero id article exists 
        # 430 no article with this id 
        pass 

class NNTP_Client(socketserver.StreamRequestHandler): 

    objProtocole = None
    continuer = True

    debug = True
    
    def envoyer(self, m):
        if isinstance(m, str): 
            m = (m,)
        for ligne in m:
            if self.debug:
                logging.debug(
                    "[%s:%s] <<<\t %s" % (
                        *self.client_address,
                        ligne
                    ) 
                ) 
            self.wfile.write( 
                (ligne.strip()+"\r\n").encode("utf-8") 
            ) 

    def recevoir(self):
        try:
            ligne = self.rfile.readline() 
            ligne = ligne.decode("utf-8").strip() 
            if self.debug:
                logging.debug( 
                    "[%s:%s] >>>\t %s" % (
                        *self.client_address,
                        ligne
                    ) 
                ) 
            return ligne
        except UnicodeDecodeError:
            return False  

    def stopper(self):
        logging.debug( 
            "[%s:%s] ===\t stop" % self.client_address 
        ) 
        self.continuer = False 

    def handle(self):  
        logging.info(
            "[%s:%s] client entrant" % self.client_address
        ) 
        self.objProtocole = NNTP_Protocole( 
            self 
        ) 
        while self.continuer: 
            self.objProtocole.resoudre() 
        logging.info(
            "[%s:%s] client sortant" % self.client_address
        ) 
            
class Serveur(socketserver.TCPServer):

    allow_reuse_address = True 

if __name__ == "__main__": 
    try: 
        hote, port = "localhost", 9999 
        with Serveur( 
            (hote, port),
            NNTP_Client
        ) as serveur: 
            logging.info( 
                "service démarré sur %s:%s" % (hote, port)
            ) 
            serveur.serve_forever()
        logging.debug("service arrêté")
    except KeyboardInterrupt: 
        logging.info("fin du programme (interruption clavier)")
    except Exception as err:
        print(err) 
        logging.info("fin du programme (erreur fatale)") 
    finally: 
        logging.debug("/!-fin\ fin des logs") 



    
