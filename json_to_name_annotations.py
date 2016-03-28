import json as JSON
import codecs
from argparse import ArgumentParser
from sys import stdout,stdin,stderr

scriptArgs = ArgumentParser()
scriptArgs.add_argument("--inputs",nargs='*',help="File containing a JSON list of JSON annotation objects.")
scriptArgs.add_argument("--output",help="Output file which will have lines <token><tab><label>, one token/label pair per line.")
scriptArgs.add_argument("--iob",action='store_true',help="Add 'B_' and 'I_' prefixes to name labels for IOB annotation, vs. the default IO.")
scriptArgs.add_argument("--nametypes",help="List of entity types to restrict to, comma-separated.  Optional; not really needed anymore.")

argValues = scriptArgs.parse_args()

inputFiles = argValues.inputs
outputFile = argValues.output
useIOB     = argValues.iob
onlyTypes  = None

if (argValues.nametypes is not None):
    onlyTypes = set(argValues.nametypes.split(","))

outputNameTypes = set()

# Not using these right now
excludeTokens = set("&lt;br&gt; &lt;br/&gt; &amp; &amp;#039; &lt;/a&gt;".split())

##############################################################

def main ():
    nonOverlapping(inputFiles,[outputFile])
    if (outputFile is not None):
        outstream = codecs.open(outputFile,"wb","utf-8")
    else:
        outstream = stdout
    if (inputFiles):
        for inputFile in inputFiles:
            processJSONFile(inputFile,outstream)
    else:
        processJSONStream(stdin,outstream)
    if (outstream != stdout):
        outstream.close()
    stderr.write("\nName types found: %s\n" % " ".join(outputNameTypes))

def processJSONFile (inputFile,outstream):
    """Takes a file containing a JSON list, and and an output stream."""
    instream = codecs.open(inputFile,"rb","utf-8")
    processJSONStream(instream,outstream)
    instream.close()

def processJSONStream (instream,outstream):
    """Takes an input stream, on which a JSON list is assumed to be, and an output stream.
       Generates the annotation from the JSON list and writes it to outputstream."""
    forms = JSON.load(instream)
    processJSONForms(forms,outstream)

def processJSONForms (forms,outstream):
    """Takes a JSON list, and an output stream.  Generates the annotation from the JSON list
       and writes it to the output stream."""
    assert(type(forms) == list)
    # print("%d forms" % len(forms))
    for form in forms:
        assert(type(form) == dict)
        sentTokens = form["allTokens"]
        assert(type(sentTokens) == list)
        for i,token in enumerate(sentTokens):
            if (" " in token or "\t" in token):
                sentTokens[i] = "_BAD_"            
        sentLen    = len(sentTokens)
        assert(sentLen > 0)
        annotSet   = form["annotationSet"]        
        assert(type(annotSet) == dict)
        # Collect up all the entities that were identified for this sentence
        entities = []
        for labelType,annots in annotSet.iteritems():
            if (labelType == "noAnnotations" or 
                (onlyTypes is not None and labelType not in onlyTypes)):
                continue
            assert(type(annots) == list)
            for annot in annots:
                assert(type(annot) == dict)
                annotTokens = annot["annotatedTokens"]
                assert(type(annotTokens) == list)
                assert(len(annotTokens) > 0)
                start         = int(annot["start"])
                assert(start >= 0 and start < sentLen)
                end           = start + len(annotTokens)-1
                entity        = Entity()
                entity.type   = labelType
                entity.start  = start
                entity.end    = end
                entity.tokens = sentTokens[start:end+1]
                entity.string = " ".join(entity.tokens)
                entities.append(entity)
                outputNameTypes.add(labelType)
        # Generate labels for them and print them out one per line
        labels = generateLabelsForSentence(sentTokens,entities)
        # Don't filter right now 
        # (sentTokens,labels) = filterTokens(sentTokens,labels)
        for i in range(0,len(labels)):
            # outstream.write("%s\t%s\n" % (sentTokens[i].encode("utf-8"),labels[i]))
            # outstream.write("%s\t%s\n" % (sentTokens[i],labels[i]))
            token = fixToken(sentTokens[i])
            tmp = token
            tmp += unicode("\t")
            tmp += unicode(labels[i])
            tmp += unicode("\n")
            if ("\t" not in tmp):
                raise "Huh?"
            outstream.write(tmp)
            # outstream.write(sentTokens[i])
            # outstream.write(unicode("\t"))
            # outstream.write(labels[i])
            # outstream.write("\n")
        # Last line must be empty with newline.     
        outstream.write("\n")

def fixToken (token):
    hasWhite = False
    for char in token:
        if (shouldRemoveChar(char)):
            hasWhite = True
            break
    if (hasWhite):
        newToken = ""
        for char in token:
            if (not shouldRemoveChar(char)):
                newToken += char
        if (newToken == ""):
            newToken = "__BAD__"
        return newToken
    else:
        return token

def shouldRemoveChar (char):
    # return (char.isspace() or char == u"\u009c")
    return char.isspace()

def filterTokens (tokens,labels):
    validIndices = []
    for i in range(0,len(tokens)):
        token = tokens[i]
        label = labels[i]
        if (token not in excludeTokens or label != "O"):
            validIndices.append(i)
    newTokens = []
    newLabels = []
    for idx in validIndices:
        newTokens.append(tokens[idx])
        newLabels.append(labels[idx])
    return (newTokens,newLabels)

def generateLabelsForSentence (words,entities):
    labels = ["O"] * len(words)
    for e in entities:
        for i in range(e.start,e.end+1):
            label = e.type
            if (useIOB):
                prefix = "B_" if i == e.start else "I_"
                label = prefix + label
            if (e.end >= len(labels)):
                raise RuntimeError(format("'%s' %s %d:%d %s" % (" ".join(words),e.type,e.start,e.end,e.string)))
            labels[i] = label
    return labels

def split (strg,sep=" "):
    tokens = []
    for tok in strg.split(sep):
        if (tok != ""):
            tokens.append(tok)
    return tokens


def nonOverlapping (files1, files2):
    """Takes two lists of files; raises an exception if they overlap."""
    if (files1 is None or files2 is None):
        return
    for file1 in files1:
        for file2 in files2:
            if (file1 != None and file2 != None and file1 == file2):
                raise RuntimeError(format("Can't overwrite %s" % file1)) 
        
class Entity:
    def __init__ (self):
        self.type   = None
        self.start  = None
        self.end    = None
        self.worker = None  
        self.tokens = None
        self.string = None

######################################

if (__name__ == "__main__"):
    main()
