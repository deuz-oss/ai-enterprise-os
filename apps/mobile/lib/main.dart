import 'package:flutter/material.dart';

void main() {
  runApp(const AiEnterpriseMobileApp());
}

class AiEnterpriseMobileApp extends StatelessWidget {
  const AiEnterpriseMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI Enterprise OS',
      theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
      home: const Scaffold(
        body: Center(
          child: Text('AI Enterprise OS Mobile Foundation'),
        ),
      ),
    );
  }
}
