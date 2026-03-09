"""
Seed script — populates Qdrant with Indian law content.
Strategy:
  1. Try to fetch from open/mirror sources (no bot blocking)
  2. Fall back to hardcoded key sections (always works offline too)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import requests
from bs4 import BeautifulSoup
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from backend.deps import get_qdrant_client, get_embeddings
from backend.config import settings
from langchain_qdrant import QdrantVectorStore
from pymongo import MongoClient

# ── helpers ──────────────────────────────────────────────────────────────────

def get_vector_store():
    client = get_qdrant_client()
    embeddings = get_embeddings()
    return QdrantVectorStore(
        client=client,
        collection_name=settings.qdrant_collection,
        embedding=embeddings,
    )

def get_mongo():
    client = MongoClient(settings.mongo_uri)
    return client[settings.mongo_db]

def chunk_documents(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    return splitter.split_documents(docs)

def ingest(docs: list[Document], act_name: str, db) -> int:
    if not docs:
        return 0
    chunks = chunk_documents(docs)
    vs = get_vector_store()
    vs.add_documents(chunks)
    # Save metadata to MongoDB — use a stable string _id (never ObjectId)
    import uuid as _uuid
    doc_id = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, act_name))
    db.documents.update_one(
        {"title": act_name},
        {
            "$set": {
                "title": act_name,
                "source_type": "seeded",
                "chunk_count": len(chunks),
                "status": "complete",
            },
            "$setOnInsert": {"_id": doc_id},
        },
        upsert=True,
    )
    return len(chunks)

# ── online fetchers (open sources, no bot blocking) ──────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch_from_url(url: str, act_name: str, section_selector: str = "p") -> list[Document]:
    """Generic fetcher — returns list of Documents or empty list on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove nav/footer/scripts
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        paragraphs = soup.find_all(section_selector)
        text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40)
        if len(text) < 200:
            return []
        return [Document(page_content=text, metadata={"act_name": act_name, "source_url": url, "source_type": "web"})]
    except Exception as e:
        print(f"      fetch failed: {e}")
        return []

def fetch_wikipedia(title: str, act_name: str) -> list[Document]:
    """Wikipedia API — always open, no bot blocking."""
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        summary = resp.json().get("extract", "")

        # Also try full page sections via parse API
        parse_url = (
            f"https://en.wikipedia.org/w/api.php?action=query&titles={title}"
            f"&prop=extracts&explaintext=1&format=json"
        )
        parse_resp = requests.get(parse_url, headers=HEADERS, timeout=15)
        pages = parse_resp.json().get("query", {}).get("pages", {})
        full_text = ""
        for page in pages.values():
            full_text = page.get("extract", "")
            break

        content = full_text if len(full_text) > len(summary) else summary
        if len(content) < 100:
            return []
        return [Document(
            page_content=content,
            metadata={"act_name": act_name, "source_url": f"https://en.wikipedia.org/wiki/{title}", "source_type": "wikipedia"}
        )]
    except Exception as e:
        print(f"      wikipedia fetch failed: {e}")
        return []

# ── hardcoded fallback content ────────────────────────────────────────────────
# Key sections of major Indian laws — always available offline

HARDCODED_LAWS = {

    "Indian Penal Code (IPC) 1860": """
INDIAN PENAL CODE, 1860

CHAPTER I — INTRODUCTION
Section 1: Title and extent of operation of the Code.
This Act shall be called the Indian Penal Code, and shall extend to the whole of India except the State of Jammu and Kashmir.

Section 2: Punishment of offences committed within India.
Every person shall be liable to punishment under this Code and not otherwise for every act or omission contrary to the provisions thereof, of which he shall be guilty within India.

Section 4: Extension of Code to extra-territorial offences.
The provisions of this Code apply also to any offence committed by any citizen of India in any place without and beyond India.

CHAPTER III — PUNISHMENTS
Section 53: Punishments.
The punishments to which offenders are liable under the provisions of this Code are: Death, Imprisonment for life, Imprisonment (rigorous or simple), Forfeiture of property, Fine.

Section 54: Commutation of sentence of death.
In every case in which sentence of death shall have been passed, the appropriate Government may, without the consent of the offender, commute the punishment for any other punishment provided by this Code.

CHAPTER VI — OFFENCES AGAINST THE STATE
Section 121: Waging, or attempting to wage war, or abetting waging of war, against the Government of India.
Whoever wages war against the Government of India, or attempts to wage such war, or abets the waging of such war, shall be punished with death, or imprisonment for life and shall also be liable to fine.

Section 124A: Sedition.
Whoever, by words, either spoken or written, or by signs, or by visible representation, or otherwise, brings or attempts to bring into hatred or contempt, or excites or attempts to excite disaffection towards the Government established by law in India, shall be punished with imprisonment for life, to which fine may be added.

CHAPTER XVI — OFFENCES AFFECTING THE HUMAN BODY
Section 299: Culpable homicide.
Whoever causes death by doing an act with the intention of causing death, or with the intention of causing such bodily injury as is likely to cause death, or with the knowledge that he is likely by such act to cause death, commits the offence of culpable homicide.

Section 300: Murder.
Except in the cases hereinafter excepted, culpable homicide is murder, if the act by which the death is caused is done with the intention of causing death, or if it is done with the intention of causing such bodily injury as the offender knows to be likely to cause the death of the person to whom the harm is caused.

Section 302: Punishment for murder.
Whoever commits murder shall be punished with death, or imprisonment for life, and shall also be liable to fine.

Section 304: Punishment for culpable homicide not amounting to murder.
Whoever commits culpable homicide not amounting to murder shall be punished with imprisonment for life, or imprisonment of either description for a term which may extend to ten years, and shall also be liable to fine.

Section 307: Attempt to murder.
Whoever does any act with such intention or knowledge, and under such circumstances that, if he by that act caused death, he would be guilty of murder, shall be punished with imprisonment of either description for a term which may extend to ten years, and shall also be liable to fine.

Section 320: Grievous hurt.
The following kinds of hurt only are designated as "grievous": Emasculation, Permanent privation of the sight of either eye, Permanent privation of the hearing of either ear, Privation of any member or joint, Destruction or permanent impairing of the powers of any member or joint, Permanent disfiguration of the head or face, Fracture or dislocation of a bone or tooth, Any hurt which endangers life or which causes the sufferer to be during the space of twenty days in severe bodily pain, or unable to follow his ordinary pursuits.

Section 354: Assault or criminal force to woman with intent to outrage her modesty.
Whoever assaults or uses criminal force to any woman, intending to outrage or knowing it to be likely that he will thereby outrage her modesty, shall be punished with imprisonment of either description for a term which may extend to two years, or with fine, or with both.

Section 375: Rape.
A man is said to commit "rape" if he — (a) penetrates his penis, to any extent, into the vagina, mouth, urethra or anus of a woman or makes her to do so with him or any other person; or (b) inserts, to any extent, any object or a part of the body, not being the penis, into the vagina, the urethra or anus of a woman or makes her to do so with him or any other person without her consent or against her will.

Section 376: Punishment for rape.
Whoever commits rape shall be punished with rigorous imprisonment of either description for a term which shall not be less than ten years, but which may extend to imprisonment for life, and shall also be liable to fine.

Section 378: Theft.
Whoever, intending to take dishonestly any moveable property out of the possession of any person without that person's consent, moves that property in order to such taking, is said to commit theft.

Section 379: Punishment for theft.
Whoever commits theft shall be punished with imprisonment of either description for a term which may extend to three years, or with fine, or with both.

Section 383: Extortion.
Whoever intentionally puts any person in fear of any injury to that person, or to any other, and thereby dishonestly induces the person so put in fear to deliver to any person any property or valuable security, or anything signed or sealed which may be converted into a valuable security, commits "extortion".

Section 390: Robbery.
In all robbery there is either theft or extortion. When theft is robbery: Theft is robbery if, in order to the committing of the theft, or in committing the theft, or in carrying away or attempting to carry away property obtained by the theft, the offender, for that end, voluntarily causes or attempts to cause to any person death or hurt or wrongful restraint, or fear of instant death or of instant hurt, or of instant wrongful restraint.

Section 395: Punishment for dacoity.
Whoever commits dacoity shall be punished with imprisonment for life, or with rigorous imprisonment for a term which may extend to ten years, and shall also be liable to fine.

Section 415: Cheating.
Whoever, by deceiving any person, fraudulently or dishonestly induces the person so deceived to deliver any property to any person, or to consent that any person shall retain any property, or intentionally induces the person so deceived to do or omit to do anything which he would not do or omit if he were not so deceived, and which act or omission causes or is likely to cause damage or harm to that person in body, mind, reputation or property, is said to "cheat".

Section 420: Cheating and dishonestly inducing delivery of property.
Whoever cheats and thereby dishonestly induces the person deceived to deliver any property to any person, or to make, alter or destroy the whole or any part of a valuable security, or anything which is signed or sealed, and which is capable of being converted into a valuable security, shall be punished with imprisonment of either description for a term which may extend to seven years, and shall also be liable to fine.

Section 499: Defamation.
Whoever, by words either spoken or intended to be read, or by signs or by visible representations, makes or publishes any imputation concerning any person intending to harm, or knowing or having reason to believe that such imputation will harm, the reputation of such person, is said, except in the cases hereinafter expected, to defame that person.

Section 500: Punishment for defamation.
Whoever defames another shall be punished with simple imprisonment for a term which may extend to two years, or with fine, or with both.

Section 503: Criminal intimidation.
Whoever threatens another with any injury to his person, reputation or property, or to the person or reputation of any one in whom that person is interested, with intent to cause alarm to that person, or to cause that person to do any act which he is not legally bound to do, or to omit to do any act which that person is legally entitled to do, as the means of avoiding the execution of such threat, commits criminal intimidation.

Section 506: Punishment for criminal intimidation.
Whoever commits the offence of criminal intimidation shall be punished with imprisonment of either description for a term which may extend to two years, or with fine, or with both.
""",

    "Code of Criminal Procedure (CrPC) 1973": """
CODE OF CRIMINAL PROCEDURE, 1973

CHAPTER I — PRELIMINARY
Section 1: Short title, extent and commencement.
(1) This Act may be called the Code of Criminal Procedure, 1973.
(2) It extends to the whole of India except the State of Jammu and Kashmir.

Section 2: Definitions.
In this Code, unless the context otherwise requires—
"bailable offence" means an offence which is shown as bailable in the First Schedule, or which is made bailable by any other law for the time being in force;
"non-bailable offence" means any other offence;
"cognizable offence" means an offence for which, and "cognizable case" means a case in which, a police officer may, in accordance with the First Schedule or under any other law for the time being in force, arrest without warrant;
"non-cognizable offence" means an offence for which, and "non-cognizable case" means a case in which, a police officer has no authority to arrest without warrant.

CHAPTER V — ARREST OF PERSONS
Section 41: When police may arrest without warrant.
Any police officer may without an order from a Magistrate and without a warrant, arrest any person—
(a) who commits a cognizable offence in the presence of a police officer;
(b) against whom a reasonable complaint has been made, or credible information has been received, or a reasonable suspicion exists that he has committed a cognizable offence punishable with imprisonment for a term which may be less than seven years or which may extend to seven years whether with or without fine.

Section 46: Arrest how made.
(1) In making an arrest the police officer or other person making the same shall actually touch or confine the body of the person to be arrested, unless there be a submission to the custody by word or action.
(2) If such person forcibly resists the endeavour to arrest him, or attempts to evade the arrest, such police officer or other person may use all means necessary to effect the arrest.
(3) Nothing in this section gives a right to cause the death of a person who is not accused of an offence punishable with death or with imprisonment for life.

Section 50: Person arrested to be informed of grounds of arrest and of right to bail.
(1) Every police officer or other person arresting any person without warrant shall forthwith communicate to him full particulars of the offence for which he is arrested or other grounds for such arrest.
(2) Where a police officer arrests without warrant any person other than a person accused of a non-bailable offence, he shall inform the person arrested that he is entitled to be released on bail and that he may arrange for sureties on his behalf.

Section 57: Person arrested not to be detained more than twenty-four hours.
No police officer shall detain in custody a person arrested without warrant for a longer period than under all the circumstances of the case is reasonable, and such period shall not, in the absence of a special order of a Magistrate under section 167, exceed twenty-four hours exclusive of the time necessary for the journey from the place of arrest to the Magistrate's Court.

CHAPTER VI — FIRST INFORMATION REPORT (FIR)
Section 154: Information in cognizable cases (FIR).
(1) Every information relating to the commission of a cognizable offence, if given orally to an officer in charge of a police station, shall be reduced to writing by him or under his direction, and be read over to the informant; and every such information, whether given in writing or reduced to writing as aforesaid, shall be signed by the person giving it, and the substance thereof shall be entered in a book to be kept by such officer in such form as the State Government may prescribe in this behalf.
(2) A copy of the information as recorded under sub-section (1) shall be given forthwith, free of cost, to the informant.
(3) Any person aggrieved by a refusal on the part of an officer in charge of a police station to record the information referred to in subsection (1) may send the substance of such information, in writing and by post, to the Superintendent of Police concerned.

Section 161: Examination of witnesses by police.
(1) Any police officer making an investigation under this Chapter, or any police officer not below such rank as the State Government may, by general or special order, prescribe in this behalf, acting on the requisition of such officer, may examine orally any person supposed to be acquainted with the facts and circumstances of the case.
(2) Such person shall be bound to answer truly all questions relating to such case put to him by such officer, other than questions the answers to which would have a tendency to expose him to a criminal charge or to a penalty or forfeiture.

CHAPTER XI — BAIL
Section 436: In what cases bail to be taken.
When any person other than a person accused of a non-bailable offence is arrested or detained without warrant by a police officer, or appears or is brought before a Court, and is prepared at any time while in the custody of such officer or at any stage of the proceeding before such Court to give bail, such person shall be released on bail. Provided that such officer or Court, if he or it thinks fit, instead of taking bail from such person, may discharge him on his executing a bond without sureties for his appearance.

Section 437: When bail may be taken in case of non-bailable offence.
When any person accused of, or suspected of, the commission of any non-bailable offence is arrested or detained without warrant by a police officer, or appears or is brought before a Court other than the High Court or Court of Session, he may be released on bail.

Section 438: Direction for grant of bail to person apprehending arrest (Anticipatory Bail).
(1) When any person has reason to believe that he may be arrested on accusation of having committed a non-bailable offence, he may apply to the High Court or the Court of Session for a direction under this section that in the event of such arrest he shall be released on bail; and that Court may, after taking into consideration, inter alia, the following factors, namely—
(i) the nature and gravity of the accusation;
(ii) the antecedents of the applicant including the fact as to whether he has previously undergone imprisonment on conviction by a Court in respect of any cognizable offence;
(iii) the possibility of the applicant to flee from justice; and
(iv) where the accusation appears to have been made with the object of injuring or humiliating the applicant by having him so arrested.

Section 439: Special powers of High Court or Court of Session regarding bail.
(1) A High Court or Court of Session may direct—
(a) that any person accused of an offence and in custody be released on bail, and if the offence is of the nature specified in subsection (3) of section 437, may impose any condition which it considers necessary for the purposes mentioned in that subsection;
(b) that any condition imposed by a Magistrate when releasing any person on bail be set aside or modified.
""",

    "Constitution of India — Fundamental Rights": """
CONSTITUTION OF INDIA

PART III — FUNDAMENTAL RIGHTS

Article 12: Definition of State.
In this Part, unless the context otherwise requires, "the State" includes the Government and Parliament of India and the Government and the Legislature of each of the States and all local or other authorities within the territory of India or under the control of the Government of India.

Article 13: Laws inconsistent with or in derogation of the fundamental rights.
(1) All laws in force in the territory of India immediately before the commencement of this Constitution, in so far as they are inconsistent with the provisions of this Part, shall, to the extent of such inconsistency, be void.
(2) The State shall not make any law which takes away or abridges the rights conferred by this Part and any law made in contravention of this clause shall, to the extent of the contravention, be void.

Article 14: Equality before law.
The State shall not deny to any person equality before the law or the equal protection of the laws within the territory of India.

Article 15: Prohibition of discrimination on grounds of religion, race, caste, sex or place of birth.
(1) The State shall not discriminate against any citizen on grounds only of religion, race, caste, sex, place of birth or any of them.
(2) No citizen shall, on grounds only of religion, race, caste, sex, place of birth or any of them, be subject to any disability, liability, restriction or condition with regard to— (a) access to shops, public restaurants, hotels and places of public entertainment; or (b) the use of wells, tanks, bathing ghats, roads and places of public resort maintained wholly or partly out of State funds or dedicated to the use of the general public.

Article 16: Equality of opportunity in matters of public employment.
(1) There shall be equality of opportunity for all citizens in matters relating to employment or appointment to any office under the State.
(2) No citizen shall, on grounds only of religion, race, caste, sex, descent, place of birth, residence or any of them, be ineligible for, or discriminated against in respect of, any employment or appointment to any office under the State.

Article 17: Abolition of Untouchability.
"Untouchability" is abolished and its practice in any form is forbidden. The enforcement of any disability arising out of "Untouchability" shall be an offence punishable in accordance with law.

Article 18: Abolition of titles.
(1) No title, not being a military or academic distinction, shall be conferred by the State.
(2) No citizen of India shall accept any title from any foreign State.

Article 19: Protection of certain rights regarding freedom of speech, etc.
(1) All citizens shall have the right— (a) to freedom of speech and expression; (b) to assemble peaceably and without arms; (c) to form associations or unions; (d) to move freely throughout the territory of India; (e) to reside and settle in any part of the territory of India; (f) to practise any profession, or to carry on any occupation, trade or business.
(2) Nothing in sub-clause (a) of clause (1) shall affect the operation of any existing law, or prevent the State from making any law, in so far as such law imposes reasonable restrictions on the exercise of the right conferred by the said sub-clause in the interests of the sovereignty and integrity of India, the security of the State, friendly relations with foreign States, public order, decency or morality or in relation to contempt of court, defamation or incitement to an offence.

Article 20: Protection in respect of conviction for offences.
(1) No person shall be convicted of any offence except for violation of a law in force at the time of the commission of the act charged as an offence, nor be subjected to a penalty greater than that which might have been inflicted under the law in force at the time of the commission of the offence.
(2) No person shall be prosecuted and punished for the same offence more than once (Double Jeopardy).
(3) No person accused of any offence shall be compelled to be a witness against himself (Right against Self-incrimination).

Article 21: Protection of life and personal liberty.
No person shall be deprived of his life or personal liberty except according to procedure established by law.

Article 21A: Right to education.
The State shall provide free and compulsory education to all children of the age of six to fourteen years in such manner as the State may, by law, determine.

Article 22: Protection against arrest and detention in certain cases.
(1) No person who is arrested shall be detained in custody without being informed, as soon as may be, of the grounds for such arrest nor shall he be denied the right to consult, and to be defended by, a legal practitioner of his choice.
(2) Every person who is arrested and detained in custody shall be produced before the nearest magistrate within a period of twenty-four hours of such arrest excluding the time necessary for the journey from the place of arrest to the court of the magistrate and no such person shall be detained in custody beyond the said period without the authority of a magistrate.

Article 23: Prohibition of traffic in human beings and forced labour.
(1) Traffic in human beings and begar and other similar forms of forced labour are prohibited and any contravention of this provision shall be an offence punishable in accordance with law.

Article 24: Prohibition of employment of children in factories, etc.
No child below the age of fourteen years shall be employed to work in any factory or mine or engaged in any other hazardous employment.

Article 25: Freedom of conscience and free profession, practice and propagation of religion.
(1) Subject to public order, morality and health and to the other provisions of this Part, all persons are equally entitled to freedom of conscience and the right freely to profess, practise and propagate religion.

Article 32: Remedies for enforcement of rights conferred by this Part (Right to Constitutional Remedies).
(1) The right to move the Supreme Court by appropriate proceedings for the enforcement of the rights conferred by this Part is guaranteed.
(2) The Supreme Court shall have power to issue directions or orders or writs, including writs in the nature of habeas corpus, mandamus, prohibition, quo warranto and certiorari, whichever may be appropriate, for the enforcement of any of the rights conferred by this Part.
""",

    "Right to Information (RTI) Act 2005": """
RIGHT TO INFORMATION ACT, 2005

CHAPTER I — PRELIMINARY
Section 1: Short title, extent and commencement.
(1) This Act may be called the Right to Information Act, 2005.
(2) It extends to the whole of India except the State of Jammu and Kashmir.
(3) The provisions of sub-section (1) of section 4, sub-sections (1) and (2) of section 5, sections 12, 13, 15, 16, 24, 27 and 28 shall come into force at once, and the remaining provisions of this Act shall come into force on the one hundred and twentieth day of its enactment.

Section 2: Definitions.
"information" means any material in any form, including records, documents, memos, e-mails, opinions, advices, press releases, circulars, orders, logbooks, contracts, reports, papers, samples, models, data material held in any electronic form and information relating to any private body which can be accessed by a public authority under any other law for the time being in force;
"public authority" means any authority or body or institution of self-government established or constituted by or under the Constitution; by any other law made by Parliament; by any other law made by State Legislature.
"right to information" means the right to information accessible under this Act which is held by or under the control of any public authority and includes the right to inspect work, documents, records; take notes, extracts or certified copies of documents or records; take certified samples of material; obtain information in the form of diskettes, floppies, tapes, video cassettes or in any other electronic mode or through printouts where such information is stored in a computer or in any other device.

CHAPTER II — RIGHT TO INFORMATION AND OBLIGATIONS OF PUBLIC AUTHORITIES
Section 3: Right to information.
Subject to the provisions of this Act, all citizens shall have the right to information.

Section 4: Obligations of public authorities.
(1) Every public authority shall—
(a) maintain all its records duly catalogued and indexed in a manner and the form which facilitates the right to information under this Act and ensure that all records that are appropriate to be computerised are, within a reasonable time and subject to availability of resources, computerised and connected through a network all over the country on different systems so that access to such records is facilitated;
(b) publish within one hundred and twenty days from the enactment of this Act: (i) the particulars of its organisation, functions and duties; (ii) the powers and duties of its officers and employees; (iii) the procedure followed in the decision making process, including channels of supervision and accountability.

Section 6: Request for obtaining information.
(1) A person, who desires to obtain any information under this Act, shall make a request in writing or through electronic means in English or Hindi or in the official language of the area in which the application is being made, accompanying such fee as may be prescribed, to—
(a) the Central Public Information Officer or State Public Information Officer, as the case may be, of the concerned public authority;
(b) the Central Assistant Public Information Officer or State Assistant Public Information Officer, as the case may be.
(2) An applicant making request for information shall not be required to give any reason for requesting the information or any other personal details except those that may be necessary for contacting him.

Section 7: Disposal of request.
(1) Subject to the proviso to sub-section (2) of section 5 or the proviso to sub-section (3) of section 6, the Central Public Information Officer or State Public Information Officer, as the case may be, on receipt of a request under section 6 shall, as expeditiously as possible, and in any case within thirty days of the receipt of the request, either provide the information on payment of such fee as may be prescribed or reject the request for any of the reasons specified in sections 8 and 9.
Provided that where the information sought for concerns the life or liberty of a person, the same shall be provided within forty-eight hours of the receipt of the request.

Section 8: Exemption from disclosure of information.
(1) Notwithstanding anything contained in this Act, there shall be no obligation to give any citizen—
(a) information, disclosure of which would prejudicially affect the sovereignty and integrity of India, the security, strategic, scientific or economic interests of the State, relation with foreign State or lead to incitement of an offence;
(b) information which has been expressly forbidden to be published by any court of law or tribunal or the disclosure of which may constitute contempt of court;
(c) information, the disclosure of which would cause a breach of privilege of Parliament or the State Legislature;
(d) information including commercial confidence, trade secrets or intellectual property, the disclosure of which would harm the competitive position of a third party, unless the competent authority is satisfied that larger public interest warrants the disclosure of such information.

Section 19: Appeal.
(1) Any person who, does not receive a decision within the time specified in sub-section (1) or clause (a) of sub-section (3) of section 7, or is aggrieved by a decision of the Central Public Information Officer or State Public Information Officer, as the case may be, may within thirty days from the expiry of such period or from the receipt of such a decision prefer an appeal to such officer who is senior in rank to the Central Public Information Officer or State Public Information Officer as the case may be, in each public authority.

Section 20: Penalties.
(1) Where the Central Information Commission or the State Information Commission, as the case may be, at the time of deciding any complaint or appeal is of the opinion that the Central Public Information Officer or the State Public Information Officer, as the case may be, has, without any reasonable cause, refused to receive an application for information or has not furnished information within the time specified under sub-section (1) of section 7 or malafidely denied the request for information or knowingly given incorrect, incomplete or misleading information or destroyed information which was the subject of the request or obstructed in any manner in furnishing the information, it shall impose a penalty of two hundred and fifty rupees each day till the application is received or information is furnished, so however, the total amount of such penalty shall not exceed twenty-five thousand rupees.
""",

    "Consumer Protection Act 2019": """
CONSUMER PROTECTION ACT, 2019

CHAPTER I — PRELIMINARY
Section 1: Short title, extent and commencement.
(1) This Act may be called the Consumer Protection Act, 2019.
(2) It extends to the whole of India.

Section 2: Definitions.
"complaint" means any allegation in writing, made by a complainant for obtaining any relief, that—
(i) an unfair contract or unfair trade practice or restrictive trade practice has been adopted by any trader or service provider;
(ii) the goods bought by him or agreed to be bought by him suffer from one or more defects;
(iii) the services hired or availed of or agreed to be hired or availed of by him suffer from deficiency in any respect;
(iv) a trader or a service provider, as the case may be, has charged for the goods or for the services mentioned in the complaint, a price in excess of the price fixed by or under any law for the time being in force or displayed on the goods or any package containing such goods.
"consumer" means any person who—
(i) buys any goods for a consideration which has been paid or promised or partly paid and partly promised, or under any system of deferred payment and includes any user of such goods other than the person who buys such goods for consideration paid or promised or partly paid or partly promised, or under any system of deferred payment, when such use is made with the approval of such person, but does not include a person who obtains such goods for resale or for any commercial purpose.
"defect" means any fault, imperfection or shortcoming in the quality, quantity, potency, purity or standard which is required to be maintained by or under any law for the time being in force or under any contract, express or implied or as is claimed by the trader in any manner whatsoever in relation to any goods or product.
"deficiency" means any fault, imperfection, shortcoming or inadequacy in the quality, nature and manner of performance which is required to be maintained by or under any law for the time being in force or has been undertaken to be performed by a person in pursuance of a contract or otherwise in relation to any service and includes any act of negligence or omission or commission by such person which causes loss or injury to the consumer.

CHAPTER II — CONSUMER PROTECTION COUNCILS

CHAPTER III — CENTRAL CONSUMER PROTECTION AUTHORITY
Section 10: Establishment of Central Consumer Protection Authority.
(1) The Central Government shall, by notification, establish with effect from such date as it may specify in that notification, a Central Consumer Protection Authority to be known as the Central Authority to regulate matters relating to violation of rights of consumers, unfair trade practices and false or misleading advertisements which are prejudicial to the interests of public and consumers and to promote, protect and enforce the rights of consumers as a class.

CHAPTER IV — CONSUMER DISPUTES REDRESSAL COMMISSION
Section 34: Jurisdiction of District Commission.
(1) Subject to the other provisions of this Act, the District Commission shall have jurisdiction to entertain complaints where the value of the goods or services paid as consideration does not exceed one crore rupees.

Section 47: Jurisdiction of State Commission.
(1) Subject to the other provisions of this Act, the State Commission shall have jurisdiction—
(a) to entertain complaints where the value of the goods or services paid as consideration exceeds rupees one crore but does not exceed rupees ten crore.
(b) to entertain appeals against the orders of any District Commission within the State.
(c) to call for the records and pass appropriate orders in any consumer dispute which is pending before or has been decided by any District Commission within the State.

Section 58: Jurisdiction of National Commission.
(1) Subject to the other provisions of this Act, the National Commission shall have jurisdiction—
(a) to entertain complaints where the value of the goods or services paid as consideration exceeds rupees ten crore.
(b) to entertain appeals against the orders of any State Commission.
(c) to call for the records and pass appropriate orders in any consumer dispute which is pending before or has been decided by any State Commission.

Section 69: Limitation period.
(1) The District Commission, the State Commission or the National Commission shall not admit a complaint unless it is filed within two years from the date on which the cause of action has arisen.
(2) Notwithstanding anything contained in sub-section (1), a complaint may be entertained after the period specified in sub-section (1), if the complainant satisfies the District Commission, the State Commission or the National Commission, as the case may be, that he had sufficient cause for not filing the complaint within such period.

Section 71: Enforcement of orders of District Commission, State Commission and National Commission.
Every order made by a District Commission, State Commission or National Commission shall be enforced by it in the same manner as if it were a decree made by a Court in a suit before it and the provisions of the Code of Civil Procedure, 1908 shall, as far as practicable, be applied to such orders.

UNFAIR TRADE PRACTICES AND REMEDIES
Types of unfair trade practices:
1. False representation about quality, quantity or grade of goods.
2. False representation about sponsorship, approval or affiliation.
3. Misleading representation about price of goods.
4. Offering gifts or prizes with the intention of not providing them.
5. Bargain sales—advertising goods at a price with no intention to sell at that price.
6. Hoarding or destruction of goods.
7. Manufacturing spurious goods.

Consumer Rights:
1. Right to be protected against the marketing of goods and services which are hazardous to life and property.
2. Right to be informed about the quality, quantity, potency, purity, standard and price of goods or services.
3. Right to be assured, wherever possible, access to a variety of goods and services at competitive prices.
4. Right to be heard and to be assured that consumer's interests will receive due consideration at appropriate forums.
5. Right to seek redressal against unfair trade practices or restrictive trade practices or unscrupulous exploitation of consumers.
6. Right to consumer education.
""",

    "Information Technology (IT) Act 2000": """
INFORMATION TECHNOLOGY ACT, 2000

CHAPTER I — PRELIMINARY
Section 1: Short title, extent, commencement and application.
(1) This Act may be called the Information Technology Act, 2000.
(2) It shall extend to the whole of India and, save as otherwise provided in this Act, it applies also to any offence or contravention thereunder committed outside India by any person.
(3) It shall come into force on such date as the Central Government may, by notification, appoint.

Section 2: Definitions.
"access" with its grammatical variations and cognate expressions means gaining entry into, instructing or communicating with the logical, arithmetical, or memory function resources of a computer, computer system or computer network;
"computer" means any electronic, magnetic, optical or other high-speed data processing device or system which performs logical, arithmetic, and memory functions by manipulations of electronic, magnetic or optical impulses, and includes all input, output, processing, storage, computer software or communication facilities which are connected or related to the computer in a computer system or computer network;
"computer network" means the interconnection of one or more computers or computer systems or communication device through the use of satellite, microwave, terrestrial line, wire, wireless or other communication media;
"cyber security" means protecting information, equipment, devices, computer, computer resource, communication device and information stored therein from unauthorised access, use, disclosure, disruption, modification or destruction;
"data" means a representation of information, knowledge, facts, concepts or instructions which are being prepared or have been prepared in a formalised manner, and is intended to be processed, is being processed or has been processed in a computer system or computer network, and may be in any form (including computer printouts, magnetic or optical storage media, punched cards, punched tapes) or stored internally in the memory of the computer.

CHAPTER IX — OFFENCES
Section 43: Penalty and compensation for damage to computer, computer system, etc.
If any person without permission of the owner or any other person who is in charge of a computer, computer system or computer network—
(a) accesses or secures access to such computer, computer system or computer network or computer resource;
(b) downloads, copies or extracts any data, computer data base or information from such computer, computer system or computer network including information or data held or stored in any removable storage medium;
(c) introduces or causes to be introduced any computer contaminant or computer virus into any computer, computer system or computer network;
(d) damages or causes to be damaged any computer, computer system or computer network, data, computer data base or any other programmes residing in such computer, computer system or computer network;
he shall be liable to pay damages by way of compensation to the person so affected.

Section 65: Tampering with computer source documents.
Whoever knowingly or intentionally conceals, destroys or alters or intentionally or knowingly causes another to conceal, destroy or alter any computer source code used for a computer, computer programme, computer system or computer network, when the computer source code is required to be kept or maintained by law for the time being in force, shall be punishable with imprisonment up to three years, or with fine which may extend up to two lakh rupees, or with both.

Section 66: Computer related offences.
If any person, dishonestly or fraudulently, does any act referred to in section 43, he shall be punishable with imprisonment for a term which may extend to three years or with fine which may extend to five lakh rupees or with both.

Section 66A: Punishment for sending offensive messages through communication service.
Any person who sends, by means of a computer resource or a communication device—
(a) any information that is grossly offensive or has menacing character; or
(b) any information which he knows to be false, but for the purpose of causing annoyance, inconvenience, danger, obstruction, insult, injury, criminal intimidation, enmity, hatred or ill will, persistently by making use of such computer resource or a communication device,
shall be punishable with imprisonment for a term which may extend to three years and with fine.
NOTE: Section 66A was struck down by the Supreme Court in Shreya Singhal v. Union of India (2015) as unconstitutional.

Section 66B: Punishment for dishonestly receiving stolen computer resource or communication device.
Whoever dishonestly receives or retains any stolen computer resource or communication device knowing or having reason to believe the same to be stolen computer resource or communication device, shall be punished with imprisonment of either description for a term which may extend to three years or with fine which may extend to rupees one lakh or with both.

Section 66C: Punishment for identity theft.
Whoever, fraudulently or dishonestly make use of the electronic signature, password or any other unique identification feature of any other person, shall be punished with imprisonment of either description for a term which may extend to three years and shall also be liable to fine which may extend to rupees one lakh.

Section 66D: Punishment for cheating by personation by using computer resource.
Whoever, by means of any communication device or computer resource cheats by personating, shall be punished with imprisonment of either description for a term which may extend to three years and shall also be liable to fine which may extend to one lakh rupees.

Section 66E: Punishment for violation of privacy.
Whoever, intentionally or knowingly captures, publishes or transmits the image of a private area of any person without his or her consent, under circumstances violating the privacy of that person, shall be punished with imprisonment which may extend to three years or with fine not exceeding two lakh rupees, or with both.

Section 66F: Punishment for cyber terrorism.
(1) Whoever— (A) with intent to threaten the unity, integrity, security or sovereignty of India or to strike terror in the people or any section of the people by— (i) denying or cause the denial of access to any person authorised to access computer resource; or (ii) attempting to penetrate or access a computer resource without authorisation or exceeding authorised access; or (iii) introducing or causing to introduce any computer contaminant, and by means of such conduct causes or is likely to cause death or injuries to persons or damage to or destruction of property or disrupts or knowing that it is likely to cause damage or disruption of supplies or services essential to the life of the community or adversely affect the critical information infrastructure; shall be punishable with imprisonment which may extend to imprisonment for life.

Section 67: Punishment for publishing obscene material in electronic form.
Whoever publishes or transmits or causes to be published or transmitted in the electronic form, any material which is lascivious or appeals to the prurient interest or if its effect is such as to tend to deprave and corrupt persons who are likely, having regard to all relevant circumstances, to read, see or hear the matter contained or embodied in it, shall be punished on first conviction with imprisonment of either description for a term which may extend to three years and with fine which may extend to five lakh rupees.

Section 72: Breach of confidentiality and privacy.
Save as otherwise provided in this Act or any other law for the time being in force, if any person who, in pursuance of any of the powers conferred under this Act, rules or regulations made thereunder, has secured access to any electronic record, book, register, correspondence, information, document or other material without the consent of the person concerned discloses such material to any other person shall be punished with imprisonment for a term which may extend to two years, or with fine which may extend to one lakh rupees, or with both.

Section 79: Exemption from liability of intermediary in certain cases.
(1) Notwithstanding anything contained in any law for the time being in force but subject to the provisions of sub-sections (2) and (3), an intermediary shall not be liable for any third party information, data, or communication link made available or hosted by him.
(2) The provisions of sub-section (1) shall apply if—
(a) the function of the intermediary is limited to providing access to a communication system over which information made available by third parties is transmitted or temporarily stored or hosted; or
(b) the intermediary does not— (i) initiate the transmission, (ii) select the receiver of the transmission, and (iii) select or modify the information contained in the transmission.
""",

    "Protection of Women from Domestic Violence Act 2005": """
PROTECTION OF WOMEN FROM DOMESTIC VIOLENCE ACT, 2005

Section 1: Short title, extent and commencement.
This Act may be called the Protection of Women from Domestic Violence Act, 2005.

Section 2: Definitions.
"aggrieved person" means any woman who is, or has been, in a domestic relationship with the respondent and who alleges to have been subjected to any act of domestic violence by the respondent;
"domestic relationship" means a relationship between two persons who live or have, at any point of time, lived together in a shared household, when they are related by consanguinity, marriage, or through a relationship in the nature of marriage, adoption or are family members living together as a joint family;
"domestic violence" has the same meaning as assigned to it in section 3;
"shared household" means a household where the person aggrieved lives or at any stage has lived in a domestic relationship either singly or along with the respondent.

Section 3: Definition of domestic violence.
For the purposes of this Act, any act, omission or commission or conduct of the respondent shall constitute domestic violence in case it—
(a) harms or injures or endangers the health, safety, life, limb or well-being, whether mental or physical, of the aggrieved person or tends to do so and includes causing physical abuse, sexual abuse, verbal and emotional abuse and economic abuse; or
(b) harasses, harms, injures or endangers the aggrieved person with a view to coerce her or any other person related to her to meet any unlawful demand for any dowry or other property or valuable security; or
(c) has the effect of threatening the aggrieved person or any person related to her by any conduct mentioned in clause (a) or clause (b); or
(d) otherwise injures or causes harm, whether physical or mental, to the aggrieved person.

Section 12: Application to Magistrate.
(1) An aggrieved person or a Protection Officer or any other person on behalf of the aggrieved person may present an application to the Magistrate seeking one or more reliefs under this Act.
(2) The relief sought under sub-section (1) may include a relief for issuance of an order for payment of compensation or damages without prejudice to the right of such person to institute a suit for compensation or damages for the injuries caused by the acts of domestic violence committed by the respondent.

Section 18: Protection orders.
The Magistrate may, after giving the aggrieved person and the respondent an opportunity of being heard and on being prima facie satisfied that domestic violence has taken place or is likely to take place, pass a protection order in favour of the aggrieved person and prohibit the respondent from—
(a) committing any act of domestic violence;
(b) aiding or abetting in the commission of acts of domestic violence;
(c) entering the place of employment of the aggrieved person or, if the person aggrieved is a child, its school or any other place frequented by the aggrieved person;
(d) attempting to communicate in any form, whatsoever, with the aggrieved person, including personal, oral or written or electronic or telephonic contact.

Section 19: Residence orders.
(1) While disposing of an application under sub-section (1) of section 12, the Magistrate may, on being satisfied that domestic violence has taken place, pass a residence order—
(a) restraining the respondent from dispossessing or in any other manner disturbing the possession of the aggrieved person from the shared household, whether or not the respondent has a legal or equitable interest in the shared household;
(b) directing the respondent to remove himself from the shared household;
(c) restraining the respondent or any of his relatives from entering any portion of the shared household in which the aggrieved person resides.

Section 20: Monetary reliefs.
(1) While disposing of an application under sub-section (1) of section 12, the Magistrate may direct the respondent to pay monetary relief to meet the expenses incurred and losses suffered by the aggrieved person and any child of the aggrieved person as a result of the domestic violence and such relief may include—
(a) the loss of earnings;
(b) the medical expenses;
(c) the loss caused due to the destruction, damage or removal of any property from the control of the aggrieved person.

Section 31: Penalty for breach of protection order by respondent.
(1) A breach of protection order, or of an interim protection order, by the respondent shall be an offence under this Act and shall be punishable with imprisonment of either description for a term which may extend to one year, or with fine which may extend to twenty thousand rupees, or with both.
""",

    "Motor Vehicles Act 1988 — Key Provisions": """
MOTOR VEHICLES ACT, 1988

Section 2: Definitions.
"accident" means an unintended sudden occurrence which causes injury or death to any person or damage to any property;
"driving licence" means the licence issued by a competent authority under Chapter II authorising the person specified therein to drive, otherwise than as a learner, a motor vehicle or a motor vehicle of any specified class or description;
"insurance" means a contract of insurance as required by this Act;

Section 3: Necessity for driving licence.
(1) No person shall drive a motor vehicle in any public place unless he holds an effective driving licence issued to him authorising him to drive the vehicle; and no person shall so drive a transport vehicle unless his driving licence specifically entitles him so to do.

Section 119: Duty to obey traffic signs.
Every driver of a motor vehicle shall drive the vehicle in conformity with any indication given by a mandatory traffic sign and shall comply with all directions given to him by any police officer for the time being engaged in regulating traffic in any public place.

Section 129: Wearing of protective headgear.
Every person driving or riding on a motorcycle of any class or description shall wear protective headgear conforming to the standards of Bureau of Indian Standards.

Section 130: Duty to produce licence and certificate of registration.
(1) The driver of a motor vehicle in any public place shall, on being so required by any police officer in uniform, produce his licence for examination.

Section 134: Duty of driver in case of accident and injury to a person.
When any person is injured or any property of a third party is damaged, as a result of an accident in which a motor vehicle is involved, the driver of the vehicle shall—
(a) unless it is not practicable to do so on account of mob fury or any other reason beyond his control, take all reasonable steps to secure medical attention for the injured person, by conveying him to the nearest medical practitioner or hospital, and it shall be the duty of every registered medical practitioner or the doctor on the duty in the hospital immediately to attend to the injured person.

Section 158: Production of certain certificates, licence and permit.
(1) Any person driving a motor vehicle in any public place shall, on being so required by a police officer in uniform, produce the certificate of insurance, the certificate of registration and the driving licence for examination.

Section 185: Driving by a drunken person or by a person under the influence of drugs.
Whoever, while driving, or attempting to drive, a motor vehicle has, in his blood, alcohol exceeding 30 mg. per 100 ml. of blood detected in a test by a breath analyser shall be punishable for the first offence with imprisonment for a term which may extend to six months, or with fine which may extend to two thousand rupees, or with both.

Section 194: Penalty for using vehicle in unsafe condition.
Whoever drives or causes or allows to be driven in any public place a motor vehicle or trailer which has any defect, which such person knows of or could have discovered by the exercise of ordinary care and which is calculated to render the driving of the vehicle a source of danger to persons and vehicles using the public place, shall be punishable with fine which may extend to five hundred rupees, or if any accident occurs resulting in bodily injury or damage to property with fine which may extend to three thousand rupees.

Hit and Run Cases:
Under Section 161 of the Motor Vehicles Act (amended), the compensation for death in hit and run cases is Rs. 2,00,000 and for grievous hurt is Rs. 50,000, payable from the Solatium Fund.
""",
}

# ── main seeder ───────────────────────────────────────────────────────────────

def seed():
    print("\n" + "═" * 55)
    print("  LawBot — Seeding legal knowledge base")
    print("═" * 55 + "\n")

    db = get_mongo()
    total_chunks = 0

    for act_name, content in HARDCODED_LAWS.items():
        print(f"▶  {act_name}")

        # Step 1: Try Wikipedia for extra context
        wiki_title = act_name.split("(")[0].strip().replace(" ", "_")
        wiki_docs = fetch_wikipedia(wiki_title, act_name)
        if wiki_docs:
            print(f"   ✓ Wikipedia context fetched ({len(wiki_docs[0].page_content)} chars)")
        else:
            print(f"   ℹ  Wikipedia not available — using hardcoded content only")

        # Step 2: Always use hardcoded content (reliable)
        hardcoded_doc = Document(
            page_content=content.strip(),
            metadata={
                "act_name": act_name,
                "source_type": "hardcoded",
                "source_url": "",
            }
        )

        # Combine hardcoded + wikipedia
        all_docs = [hardcoded_doc] + wiki_docs

        # Step 3: Ingest into Qdrant
        chunks = ingest(all_docs, act_name, db)
        total_chunks += chunks
        print(f"   ✓ Ingested — {chunks} chunks stored in Qdrant\n")

        # Small delay to avoid hammering Wikipedia
        time.sleep(1)

    print("═" * 55)
    print(f"  Done — {total_chunks} total chunks ingested")
    print(f"  Laws seeded: {len(HARDCODED_LAWS)}")
    print("═" * 55 + "\n")
    print("✅ You can now ask questions like:")
    print("   • What is Section 302 IPC?")
    print("   • What are my rights if arrested?")
    print("   • How to file an RTI application?")
    print("   • What is anticipatory bail?")
    print("   • What are consumer rights under CPA 2019?")

if __name__ == "__main__":
    seed()