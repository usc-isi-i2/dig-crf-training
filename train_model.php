<?php 
      require_once "System.php";
      set_time_limit(600);
      $trainJson =  System::mktemp();
      $jsonText  = file_get_contents($_FILES['jsonfile']['tmp_name']);
      $jsonOutput = fopen($trainJson,"w");
      fwrite($jsonOutput,$jsonText);
      fclose($jsonOutput);
      $response = shell_exec("bash train_model.sh $trainJson http://localhost");
      echo $response;
?>


