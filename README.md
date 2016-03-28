# dig-crf-training

Code for the service to train a crf given annotations

Components are as follows.  To get more information about arguments, use the --help arg.

 json_to_name_annotations.py  - Python script which takes DIG Mturk JSON output and turns it into labeled training data.

 crf_features.py	      - Python script which takes labeled training data and adds features to it.  Also produces a template file.

 dig-crf.feat-list	      - The generic feature list specification file which works well for many applications. This is data not code.
                                I've given it a generic name for generality.

 crf_learn		      - An executable which takes featurized training data and and a template file, and produces a trained model.

 crf_test		      - An executable which takes featurized data and a model, and produces labeled output.  Not used in training.

 index.html		      - A very basic HTML page with a form for POSTing a file of DIG Mturk JSON data to the server.

 train_model.php 	      - PHP script that receives the POSTed JSON, and invokes the underlying shell script, passing it a training file and URL prefix.
                                Echoes back the response from the shell script.

 train_model.sh		      - A bash script that integrates json_to_name_annotations, crf_features, and crf_learn to do the training.
                                Prints a JSON map string giving the URL to the trained model in the 'model' field, and a log file in the 'log' field.
                                If training failed for some reason (e.g. malformed input), this JSON will just contain a 'log' field.

                                This script will create a unique sub-directory inside the 'outputs' directory on the server (the 'outputs' dir must exist).
                                In this you will find 'crf.model' and 'log.txt', along with the other files that were generated as part of the training.


Formats:

 * Labeled training data: This format is just tab-separated lines of the form

    token<tab>label

  where the label is either 'O', or one of the name types, e.g. 'hairType', 'eyeColor', etc.  
  For each token in the message text to be tagged, there is one such line.  A blank line
  signifies the end of the message.  Labeled training data thus consists of many lines.


 * Featurized training data: This format is like labeled training data, except with features inserted between the token and label:

    token<tab>feat1<tab>feat2<tab>...<tab>featn<tab><label>

 * crf_test output: This is just like the featurized training data, except that the label at the end corresponds to the label that was
   inferred by the program.  If it's test data for which the true labels are known, you can have two labels, the first being the correct one
   and the second the system output.  Extra columns in the feature matrix, like a column for the true_label, don't bother crf_test.

    token<tab>feat1<tab>feat2<tab>...<tab>featn<tab><true_label><tab><system_label>

 * Template file: This is automatically produced by crf_features from the feature specification file (here, dig-crf.feat-list).
   It's not really human-readable, but crf_learn needs it to work.  It shouldn't be neccesary for humans to deal with this.


Training with the server:

 * You can use a form like:

     curl -F "jsonfile=@your_file_name" http://url_path/train_model.php

   Where 'your_file_name' is the file of JSON you want to use, and 'url_path' is the URL where the server code resides.
   This will return a JSON:

    {"model": "http://url_path/outputs/UNIQUE_NAME/crf.model", "log": "http://url_path/outputs/UNIQUE_NAME/log.txt"}

   The UNIQUE_NAME will be a randomly-generated unique sub-directory in the 'outputs' directory.  To fetch the model,
   just do a GET on this model URL, which you can do with:

    curl http://url_path/outputs/UNIQUE_NAME/crf.model > your_model_file

   Getting the log file is similar.  If the training failed for some reason, there will be no model, just the log file.  In 
   this case, the log file will be important to you for figuring out what happened.


Decoding:

 * Turn the message into the one-line-per-token format, with blank line denoting end of the message, and pass to crf_features.
   Make sure to give crf_features the same feature spec file that the model was trained with!  That's why I've given it the generic
   name dig-crf.feat-list.  I currently don't have serverization for decoding.  