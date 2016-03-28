# Inputs: Input file and prefix for result URL 

INPUT=$1
URL_PREFIX=$2

# Codes for HTTP response. 

SUCCESS_CODE=200
FAILURE_CODE=400

# Directory for scripts, code, and script data files

BIN=bin

# The input feature-specification file which is constant for all invocations, currently.

FEAT_LIST=$BIN/dig-crf.feat-list


# Flag arguments to the different components.  

LABEL_FLAGS=""
FEAT_FLAGS="--labeled --featlist $FEAT_LIST"
TRAIN_FLAGS="-f 1 -a CRF-L2"


# Make a unique output directory for this invocation

OUTDIR=$(mktemp -d -p output)

# The intermediate files in OUTDIR

TRAIN_JSON="$OUTDIR/training.json"
TRAIN_LABELS="$OUTDIR/training.labeled"
TRAIN_FEATS=$OUTDIR/training.feats
TEMPLATES=$OUTDIR/training.templates
LOG_FILE="$OUTDIR/log.txt"

# The result file in OUTDIR

MODEL=$OUTDIR/crf.model


echo "INPUT: $INPUT" &>>$LOG_FILE

# Copy the temporary input file to TRAIN_JSON

cp $INPUT $TRAIN_JSON &>>$LOG_FILE

# Convert the JSON into name annotations

python -u $BIN/json_to_name_annotations.py --inputs $TRAIN_JSON --output $TRAIN_LABELS $LABEL_FLAGS &>>$LOG_FILE

# Featurize the name annotations

python -u $BIN/crf_features.py --input $TRAIN_LABELS --output $TRAIN_FEATS --templates $TEMPLATES $FEAT_FLAGS &>>$LOG_FILE

# Train the model on the features

crf_learn $TRAIN_FLAGS $TEMPLATES $TRAIN_FEATS $MODEL &>>$LOG_FILE


# If the model file exists, we have succeeded. Emit 200 on stderr.
if [ -e $MODEL ]
then
    echo "SUCCESS" &>>$LOG_FILE
    echo "{\"model\": \"$URL_PREFIX/$MODEL\", \"log\": \"$URL_PREFIX/$LOG_FILE\"}"
    >&2 echo $SUCCESS_CODE 
# Otherwise, we have failed. Output failure code on stderr
else
    echo "FAILURE" &>>$LOG_FILE
    echo "{\"logf\": \"$URL_PREFIX/$LOG_FILE\"}"
    >&2 echo $FAILURE_CODE
fi






