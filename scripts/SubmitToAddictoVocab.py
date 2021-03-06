import os
import csv
import urllib.request
import json
import re
import requests
import traceback
import pronto


AOVOCAB_API = "https://api.addictovocab.org/"
GET_TERMS = "terms?label={}&page={}&itemsPerPage={}"
POST_TERMS = "terms"
DELETE_TERMS = "terms/{}"
PATCH_TERMS = "terms/{}"

def getAllIDsFromAddictOVocab():
    pageNo = 1
    totPerPage = 50
    allIds = []

    while (True):
        result = getFromAddictOVocab('',pageNo,totPerPage)
        resultCount = result['hydra:totalItems']

        if resultCount == 0:
            break

        for term in result['hydra:member']:
            allIds.append(term['id'])
        print(f"There are {resultCount} total results, we have {len(allIds)} so far.")

        if resultCount == len(allIds):
            break

        if (pageNo*totPerPage) > resultCount:
            break

        pageNo = pageNo + 1

    return(allIds)



def getFromAddictOVocab(label,pageNo=1,totPerPage=30):
    urlstring = AOVOCAB_API + GET_TERMS.format(label,pageNo,totPerPage)
    print(urlstring)

    r = requests.get(urlstring)
    print(f"Get returned {r.status_code}")
    return ( r.json() )

def getURIForID(id, prefix_dict):
    if "ADDICTO" in id:
        return "http://addictovocab.org/"+id
    else:
        if ":" in id:
            id_split = id.split(":")
        elif "_" in id:
            id_split = id.split("_")
        else:
            print(f"Cannot determine prefix in {id}, just returning id")
            return(id)
        prefix=id_split[0]
        if prefix in prefix_dict:
            uri_prefix = prefix_dict[prefix]
            return (uri_prefix + "_" +id_split[1])
        else:
            print("Prefix ",prefix,"not in dict")
            return (id)


# By default, don't create links the first time we create terms.
# Call a second time (after all data created) to create links.
# Can be done in one step if the linked entities do exist.
def createTermInAddictOVocab(header,rowdata, prefix_dict, create=True,links=False,revision_msg="Minor update"):
    data = {}
    for (value, headerval) in zip(rowdata,header):
        if value:
            if headerval == "ID":
                data['id'] = value
                data['uri'] = getURIForID(value, prefix_dict)
            elif headerval == "Label":
                data['label'] = value
            elif headerval == "Definition":
                data['definition'] = value
            elif headerval == "Definition source":
                data['definitionSource'] = value
            elif headerval == "Logical definition":
                data['logicalDefinition'] = value
            elif headerval == "Informal definition":
                data['informalDefinition'] = value
            elif headerval == "AO sub-ontology":
                data['addictoSubOntology'] = value
            elif headerval == "Curator note":
                data['curatorNote'] = value
            elif headerval == "Synonyms":
                vals = value.split(";")
                data['synonyms'] = vals
            elif headerval == "Comment":
                data['comment'] = value
            elif headerval == "Examples of usage":
                data['examples'] = value
            elif headerval == "Fuzzy set":
                if value:
                    try:
                        data['fuzzySet'] = bool(int(value))
                    except ValueError:
                        data['fuzzySet'] = bool(value)
                else:
                    data['fuzzySet'] = False
            elif headerval == "E-CigO":
                if value:
                    try:
                        data['eCigO'] = bool(int(value))
                    except ValueError:
                        data['eCigO'] = bool(value)
                else:
                    data['eCigO'] = False
            elif headerval == "Curator":
                pass
            elif headerval == "Curation status":
                data['curationStatus'] = value
            elif headerval == "Why fuzzy":
                data['fuzzyExplanation'] = value
            elif headerval == "Cross reference":
                vals = value.split(";")
                data['crossReference'] = vals
            elif headerval == "BFO entity":
                pass
            elif links and headerval == "Parent":
                vals = value.split(";")
                if len(vals)==1:
                    try:
                        value=getIdForLabel(value)
                        data['parentTerm'] = f"/terms/{value}"
                    except ValueError:
                        print(f"No ID found for label {value}, skipping")
                        continue
                else:
                    for val in vals:
                        value = vals[0]
                        try:
                            value = getIdForLabel(value)
                            data['parentTerm'] = f"/terms/{value}"
                            break
                        except ValueError:
                            print(f"No ID found for value {value}, skipping...")
                            continue
                    if 'parentTerm' not in data:
                        print(f"No usable parent found for {value}.")
                        continue
            elif links and re.match("REL '(.*)'",headerval):
                rel_name = re.match("REL '(.*)'",headerval).group(1)
                vals = value.split(";")
                vals_to_add = []
                for v in vals:
                    try:
                        v = '/terms/'+getIdForLabel(v)
                        vals_to_add.append(v)
                    except ValueError:
                        print(f"No ID found for linked value {v}, skipping.")
                if len(vals_to_add)>0:
                    if 'termLinks' not in data:
                        data['termLinks'] = []
                    data['termLinks'].append({'type':rel_name,
                                          'linkedTerms':vals_to_add})
            else:
                print(f"Unknown/ignored header: '{headerval}'")

    if create:
        headers = {"accept": "application/ld+json",
               "Content-Type": "application/ld+json"}
    else:
        headers = {"accept": "application/ld+json",
               "Content-Type": "application/merge-patch+json"}
        if data['curationStatus'] == 'Published':  # Revision msg needed
            data['revisionMessage'] = revision_msg

    #print(data)

    try:
        if create:
            urlstring = AOVOCAB_API + POST_TERMS
            r = requests.post(urlstring, json = data, headers=headers)
            status = r.status_code
        else:
            urlstring = AOVOCAB_API + PATCH_TERMS.format(data['id'])
            r = requests.patch(urlstring, json = data, headers=headers)
            status = r.status_code
        print(f"Create returned {r.status_code}, {r.reason}")
        #if r.status_code in ['500',500,'400',400,'404',404]:
            #print(f"Problematic JSON: {json.dumps(data)}")
    except Exception as e:
        traceback.print_exc()
        status = None
    return ( ( status, json.dumps(data) ) )


def deleteTermFromAddictOVocab(id):
    urlstring = AOVOCAB_API + DELETE_TERMS.format(id)

    r = requests.delete(urlstring)

    print(f"Delete {id}: returned {r.status_code}")


def getDefinitionForProntoTerm(term):
    if term.definition and len(term.definition)>0:
        return (term.definition)
    annots = [a for a in term.annotations]
    for a in annots:
        if isinstance(a, pronto.LiteralPropertyValue):
            if a.property == 'IAO:0000115':  # Definition
                return (a.literal)
            if a.property == 'IAO:0000600':  # Elucidation
                return (a.literal)
    if term.comment:
        return (term.comment)
    return ("None")

# ---------- Main method execution below here ----------------

os.chdir("/Users/hastingj/Work/Onto/addiction-ontology/")

# load the dictionary for prefix to URI mapping

dict_file = 'scripts/prefix_to_uri_dictionary.csv'
prefix_dict = {}
reader = csv.DictReader(open(dict_file, 'r'))
for line in reader:
    prefix_dict[line['PREFIX']] = line['URI_PREFIX']

path = 'outputs'

addicto_files = []

for root, dirs_list, files_list in os.walk(path):
    for file_name in files_list:
        full_file_name = os.path.join(root, file_name)
        addicto_files.append(full_file_name)

entries = {}
bad_entries = []

# All the external content + hierarchy is in the file addicto_external.obo
# Must be parsed and sent to AOVocab.

externalonto = pronto.Ontology("addicto_external.obo")
for term in externalonto.terms():
    label_id_map[term.name] = term.id

# get the "ready" input data, indexed by ID
for filename in addicto_files:
    with open(filename, 'r') as csvfile:
        csvreader = csv.reader(csvfile)
        header = next(csvreader)

        for row in csvreader:
            rowdata = row
            id = rowdata[0]
            entries[id] = (header,rowdata)



### Update entries with new data
### Try to create if update fails


# now create all our entities, first without links
for (header,test_entity) in entries.values():
    # Try to patch first and only if failed try to submit with post
    (status, jsonstr) = createTermInAddictOVocab(header,test_entity,prefix_dict, create=False)
    if status != 200:
        # try submit with post
        (status, jsonstr) = createTermInAddictOVocab(header,test_entity,prefix_dict)
        if status != 201:
            id = test_entity[0]
            print (status, ": Problem creating term ",id," with JSON: ",jsonstr)
            bad_entries.append(id)

# Now create additional external entries, first without links
for term in externalonto.terms():
    try:
        id = term.id
        external_header=["ID","Label","Definition","Parent","Curation status"]
        # First round: Create those that are not in
        if id not in entries:
            label = term.name
            definition = getDefinitionForProntoTerm(term)
            parents = []
            for supercls in term.superclasses(distance=1):
                parents.append(supercls.id)
            parent = ";".join(parents)
            #print("TERM DATA: ",id,",",label,",",definition,",",parent)
            # Submit to AddictO Vocab
            (status, jsonstr) = createTermInAddictOVocab(external_header,[id,label,definition,parent,"Proposed"],prefix_dict,create=False,links=False)
            if status != 200:
                (status, jsonstr) = createTermInAddictOVocab(external_header,[id,label,definition,parent,"Proposed"],prefix_dict,create=False,links=False)
                if status != 201:
                    print (status, ": Problem creating term ",id," with JSON: ",jsonstr)
                    bad_entries.append(id)
    except ValueError:
        print("ERROR PROCESSING: ",id)
        continue

# Then add links (own entries)
for id in entries:
    (header,rowdata) = entries[id]
    # Patch it:
    (status,jsonstr) = createTermInAddictOVocab(header, rowdata, prefix_dict, create=False, links=True)
    if status != 200:
        print(status, ": Problem patching term ",id,"with JSON: ",jsonstr)
        bad_entries.append(id)
else:
    print("ID not found in entries: ",id)

# Then add links (external entries)
for term in externalonto.terms():
    try:
        id = term.id
        external_header=["ID","Label","Definition","Parent","Curation status"]
        # Second round: Should all be in. Patch with parents
        label = term.name
        definition = getDefinitionForProntoTerm(term)
        parents = []
        for supercls in term.superclasses(distance=1):
            if supercls.id != id:
                parents.append(supercls.id)
        parent = ";".join(parents)

        print("TERM DATA: ",id,",",label,",",parent)

        # Patch it:
        (status,jsonstr) = createTermInAddictOVocab(external_header, [id,label,definition,parent,"Proposed"], prefix_dict, create=False, links=True)
        if status != 200:
            print(status, ": Problem patching term ",id,"with JSON: ",jsonstr)
            bad_entries.append(id)
    except ValueError:
        print("ERROR PROCESSING: ",id)
        continue




### SUBMIT JUST ONE CHANGE TO AN ENTRY WITH A SPECIFIED ID:

# Find an entry with a given ID
# Patch it (in full) with a revision message

idtochange = 'ADDICTO:0000308' # FDA tobacco product.

idstochange = ['ADDICTO:0000308','ADDICTO:0000200','ADDICTO:0000201','ADDICTO:0000207','ADDICTO:0000295','ADDICTO:0000279','ADDICTO:0000292','ADDICTO:0000303','ADDICTO:0000305','ADDICTO:0000311']

for idtochange in idstochange:
    (header,rowdata) = entries[idtochange]
    # Patch it:
    (status,jsonstr) = createTermInAddictOVocab(header, rowdata, prefix_dict, create=False, links=True, revision_msg="Final checks completed")
    if status != 200:
        print(status, ": Problem patching term ",id,"with JSON: ",jsonstr)









