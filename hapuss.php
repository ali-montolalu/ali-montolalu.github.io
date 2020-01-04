<?php 
require 'funcition.php';

$id = $_GET["id"];
if(hapuss($id) > 0 ){
	echo "
		<script>
			alert('data berhasil dihapus!');
			document.location.href = 'data_siswa.php';
		</script> 
		";
	} else {
		echo "
		<script>
			alert('data gagal dihapus!');
			document.location.href = 'data_siswa.php';
		</script> 
		";
	}
 
 ?>