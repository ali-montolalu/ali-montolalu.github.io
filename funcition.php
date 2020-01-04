<?php 
//koneksi database
$conn = mysqli_connect("localhost","root","","latihan2");

function query($query){
	global $conn;
	$result = mysqli_query($conn, $query);
	$rows = [];
	while( $row = mysqli_fetch_assoc($result)){
		$rows[] = $row;
	}
	return $rows;
}

function tambah($data){
	global $conn;
	$soal = htmlspecialchars($data["soal"]);
	$a = htmlspecialchars($data["a"]);
	$b = htmlspecialchars($data["b"]);
	$c = htmlspecialchars($data["c"]);
	$d = htmlspecialchars($data["d"]);
	$kunci = htmlspecialchars($data["kunci"]);

	$query = "INSERT INTO soal
	VALUES
	('', '$soal', '$a', '$b', '$c', '$d', '$kunci')";
	mysqli_query($conn, $query);
	return mysqli_affected_rows($conn);
}

function hapus($id){
	global $conn;
	mysqli_query($conn, "DELETE FROM soal WHERE id=$id");
	return mysqli_affected_rows($conn);
}

function hapuss($id){
	global $conn;
	mysqli_query($conn, "DELETE FROM user WHERE id=$id");
	return mysqli_affected_rows($conn);
}

function ubah($data){
	global $conn;
	$id = $data["id"];
	$soal = htmlspecialchars($data["soal"]);
	$a = htmlspecialchars($data["a"]);
	$b = htmlspecialchars($data["b"]);
	$c = htmlspecialchars($data["c"]);
	$d = htmlspecialchars($data["d"]);
	$kunci = htmlspecialchars($data["kunci"]);

	$query = "UPDATE soal SET
			soal = '$soal',
			a = '$a',
			b = '$b',
			c = '$c',
			d = '$d',
			kunci = '$kunci'
		Where id = $id
	";
	mysqli_query($conn, $query);

	return mysqli_affected_rows($conn);
}

function registrasi($data){
	global $conn;

	$username = strtolower(stripslashes($data["username"]));
	$password = mysqli_real_escape_string($conn, $data["password"]);
	$password2 = mysqli_real_escape_string($conn, $data["password2"]);
	$level = strtolower(stripslashes($data["level"]));

	//cek username sudah ada atau belum
	$result = mysqli_query($conn, "SELECT username FROM user WHERE username = '$username'");
	
	if(mysqli_fetch_assoc($result)){
		echo "<script>
				alert('username sudah terdaftar!')
			  </script>";
			return false;
	}

	//cek konfirmasi password
	if($password !== $password2){
		echo "<script>
				alert('kofirmasi password tidak sesuai!');
			  </script>"; 
		return false;
	}

	//enkripsi password
	$password = password_hash($password, PASSWORD_DEFAULT);

	$query = "INSERT INTO user
			VALUES
			('', '$username', '$password', '$level')";
	mysqli_query($conn, $query);
	return mysqli_affected_rows($conn);
}

function r_admin($data){
	global $conn;

	$username = strtolower(stripslashes($data["username"]));
	$password = mysqli_real_escape_string($conn, $data["password"]);
	$password2 = mysqli_real_escape_string($conn, $data["password2"]);

	//cek username sudah ada atau belum
	$result = mysqli_query($conn, "SELECT username FROM admin WHERE username = '$username'");
	
	if(mysqli_fetch_assoc($result)){
		echo "<script>
				alert('username sudah terdaftar!')
			  </script>";
			return false;
	}

	//cek konfirmasi password
	if($password !== $password2){
		echo "<script>
				alert('kofirmasi password tidak sesuai!');
			  </script>"; 
		return false;
	}

	//enkripsi password
	$password = password_hash($password, PASSWORD_DEFAULT);

	//tambahkan userbaru ke database
	mysqli_query($conn, "INSERT INTO admin VALUES('', '$username', '$password')");
	return mysqli_affected_rows($conn);
}

 ?>


